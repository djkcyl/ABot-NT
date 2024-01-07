import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

import kayaku
from beanie.odm.operators.find.comparison import Eq
from httpx import AsyncClient, Request
from httpx._types import ProxiesTypes
from loguru import logger

from models.tcm.ims import IMSResponseModel
from models.tcm.tms import TMSResponseModel
from utils.config import BasicConfig
from utils.datetime import CHINA_TZ
from utils.db import ImageContentReviewLog, TextContentReviewLog

from .model import HttpProfile
from .sign import signature

config = kayaku.create(BasicConfig)


@dataclass
class TencentCloudApi:
    secret_id: str
    secret_key: str
    region: str = "ap-guangzhou"
    proxy: ProxiesTypes | None = None

    async def chat(self, text: str, session: str, bot_id: str, bot_env: str, name: str | None = None) -> str | None:
        http = HttpProfile(endpoint="tbp.tencentcloudapi.com")
        async with AsyncClient(proxies=self.proxy) as client:
            params = {
                "BotId": bot_id,
                "BotEnv": bot_env,
                "TerminalId": session,
                "InputText": text,
            }
            action = "TextProcess"
            if http.method == "GET":
                req = Request(http.method, http.url, params=params, headers={})
            elif http.method == "POST":
                req = Request(http.method, http.url, json=params, headers={})
            else:
                raise NotImplementedError(http.method)
            signature(
                self.secret_id,
                self.secret_key,
                action,
                req,
                http,
                {"api_version": "2019-06-27", "service": "tbp", "region": self.region},
            )
            try:
                resp = (await client.send(req)).json()
                if message := resp.get("Response", {}).get("ResponseText"):
                    return message.replace("小微", name) if name else message
                logger.warning(resp)
            except Exception as e:
                logger.error(repr(e))

    async def send_email(
        self,
        addr: str,
        target: list[str],
        subject: str,
        template_id: int,
        template_data: dict[str, str],
        name: str | None = None,
    ) -> dict | None:
        http = HttpProfile(endpoint="ses.tencentcloudapi.com")
        async with AsyncClient(proxies=self.proxy) as client:
            params = {
                "FromEmailAddress": f"{name} <{addr}>" if name else addr,
                "Destination": target,
                "Subject": subject,
                "ReplyToAddresses": addr,
                "Template": {"TemplateID": template_id, "TemplateData": json.dumps(template_data, ensure_ascii=False)},
            }
            action = "SendEmail"
            if http.method == "GET":
                req = Request(http.method, http.url, params=params, headers={})
            elif http.method == "POST":
                req = Request(http.method, http.url, json=params, headers={})
            else:
                raise NotImplementedError(http.method)
            signature(
                self.secret_id,
                self.secret_key,
                action,
                req,
                http,
                {"api_version": "2020-10-02", "service": "ses", "region": self.region},
            )
            try:
                resp = await client.send(req)
                return resp.json()
            except Exception as e:
                logger.error(repr(e))

    async def translate(self, text: str, lang_target: str, lang_source: str = "auto") -> dict | None:
        """
        source:
            auto: 自动识别 (识别为一种语言)
            zh: 简体中文
            zh-TW: 繁体中文
            en: 英语
            ja: 日语
            ko: 韩语
            fr: 法语
            es: 西班牙语
            it: 意大利语
            de: 德语
            tr: 土耳其语
            ru: 俄语
            pt: 葡萄牙语
            vi: 越南语
            id: 印尼语
            th: 泰语
            ms: 马来西亚语
            ar: 阿拉伯语
            hi: 印地语
        target:
            zh (简体中文) : en (英语) 、ja (日语) 、ko (韩语) 、fr (法语) 、es (西班牙语) 、it (意大利语) 、de (德语) 、tr (土耳其语) 、ru (俄语) 、pt (葡萄牙语) 、vi (越南语) 、id (印尼语) 、th (泰语) 、ms (马来语)
        """
        http = HttpProfile(endpoint="tmt.tencentcloudapi.com")
        async with AsyncClient(proxies=self.proxy) as client:
            params = {
                "SourceText": text,
                "Source": lang_source,
                "Target": lang_target,
                "ProjectId": 0,
            }
            action = "TextTranslate"
            if http.method == "GET":
                req = Request(http.method, http.url, params=params, headers={})
            elif http.method == "POST":
                req = Request(http.method, http.url, json=params, headers={})
            else:
                raise NotImplementedError(http.method)
            signature(
                self.secret_id,
                self.secret_key,
                action,
                req,
                http,
                {"api_version": "2018-03-21", "service": "tmt", "region": self.region},
            )
            try:
                resp = (await client.send(req)).json()
                if res := resp.get("Response", {}).get("TargetText"):
                    return res
                logger.warning(resp)
            except Exception as e:
                logger.error(repr(e))

    async def text_moderation(self, text: str) -> TMSResponseModel:
        content = base64.b64encode(text.encode()).decode()
        text_md5 = hashlib.sha256(text.encode()).hexdigest()

        if log := await TextContentReviewLog.find_one(Eq(TextContentReviewLog.text_md5, text_md5)):
            return log.result

        http = HttpProfile(endpoint="tms.tencentcloudapi.com")
        async with AsyncClient(proxies=self.proxy) as client:
            params = {"Content": content}
            if config.tencent_cloud.text_biztype:
                params["BizType"] = config.tencent_cloud.text_biztype
            action = "TextModeration"
            if http.method == "GET":
                req = Request(http.method, http.url, params=params, headers={})
            elif http.method == "POST":
                req = Request(http.method, http.url, json=params, headers={})
            else:
                raise NotImplementedError(http.method)
            signature(
                self.secret_id,
                self.secret_key,
                action,
                req,
                http,
                {"api_version": "2020-12-29", "service": "tms", "region": self.region},
            )
            resp = (await client.send(req)).json()
            tmsm = TMSResponseModel(**resp)
            await TextContentReviewLog.insert(
                TextContentReviewLog(
                    text_md5=text_md5,
                    review_time=datetime.now(CHINA_TZ),
                    result=tmsm,
                )
            )
            return tmsm

    async def image_moderation(
        self, *, image_data: bytes | None = None, image_url: str | None = None, image_id: str | None = None
    ) -> IMSResponseModel:
        if image_data is None and image_url is None:
            msg = "image_data and image_url cannot be None at the same time"
            raise ValueError(msg)

        async with AsyncClient(proxies=self.proxy) as client:
            if image_id is None:
                if image_data:
                    image_id = hashlib.sha256(image_data).hexdigest()
                elif image_url:
                    resp = await client.get(image_url)
                    image_data = resp.content
                    image_id = hashlib.sha256(image_data).hexdigest()
                else:
                    msg = "image_data and image_url cannot be None at the same time"
                    raise ValueError(msg)

            if log := await ImageContentReviewLog.find_one(Eq(ImageContentReviewLog.image_id, image_id)):
                return log.result

            http = HttpProfile(endpoint="ims.tencentcloudapi.com")
            if image_data:
                params = {"FileContent": base64.b64encode(image_data).decode()}
            elif image_url:
                params = {"FileUrl": image_url}
            else:
                msg = "image_data and image_url cannot be None at the same time"
                raise ValueError(msg)
            if config.tencent_cloud.image_biztype:
                params["BizType"] = config.tencent_cloud.image_biztype

            action = "ImageModeration"
            if http.method == "GET":
                req = Request(http.method, http.url, params=params, headers={})
            elif http.method == "POST":
                req = Request(http.method, http.url, json=params, headers={})
            else:
                raise NotImplementedError(http.method)
            signature(
                self.secret_id,
                self.secret_key,
                action,
                req,
                http,
                {"api_version": "2020-12-29", "service": "ims", "region": self.region},
            )
            resp = (await client.send(req)).json()
            imsm = IMSResponseModel(**resp)
            await ImageContentReviewLog.insert(
                ImageContentReviewLog(
                    image_id=image_id,
                    review_time=datetime.now(CHINA_TZ),
                    result=imsm,
                )
            )
            return imsm
