import asyncio
import base64
import contextlib
import json
import re
from io import BytesIO

import dns.resolver
from loguru import logger
from PIL import Image as IMG

from utils.message.picture import SelfPicture

from .statusping import StatusPing


def ping_status(host: str, port: int | None = None):
    if port is None:
        with contextlib.suppress(Exception):
            srv_records = dns.resolver.query(f"_minecraft._tcp.{host}", "SRV")
            for srv in srv_records:
                host = str(srv.target).rstrip(".")
                port = srv.port
                break
    status_ping = StatusPing(host, port or 25565)
    status = status_ping.get_status()
    status_str = json.dumps(status)
    status_str = re.sub(r"\\u00a7.", "", status_str)
    status: dict = json.loads(status_str)
    logger.debug(status)
    return status


def get_server_status(say: str) -> dict:
    host, _, port = say.partition(":")
    return ping_status(host, int(port) if port else None)


async def handle_favicon(status: dict, messages):
    if favicon := status.get("favicon"):
        byte_data = base64.b64decode(f"{favicon[22:-1]}=")
        img = IMG.open(BytesIO(byte_data)).convert("RGB")
        image = BytesIO()
        img.save(image, format="JPEG", quality=90)
        messages.append(await SelfPicture().from_data(image, "jpeg"))


def handle_description(status: dict, messages):
    desc = status.get("description", {})
    if isinstance(desc, str):
        desc_text = desc.strip()
    elif "text" in desc and desc.get("text"):
        desc_text = desc["text"].strip()
    elif "extra" in desc:
        desc_text = "".join(extra["text"] for extra in desc["extra"]).strip()
    elif "translate" in desc:
        desc_text = desc["translate"].strip()
    else:
        return
    messages.append(f"描述：\n{desc_text}\n")


def handle_version(status: dict, messages):
    version_name = status.get("version", {}).get("name", "")
    if "Requires" in version_name:
        sType = "Vanilla"
        sVer = version_name
    else:
        sType, _, sVer = version_name.rpartition(" ")
        sType = sType or "Vanilla"

    sDevVer = str(status.get("version", {}).get("protocol", ""))
    sPlayer = f"{status.get('players', {}).get('online', '')} / {status.get('players', {}).get('max', '')}"

    messages.extend(
        (
            f"游戏版本：{sVer}\n",
            f"协议版本：{sDevVer}\n",
            f"服务端：{sType}\n",
            f"玩家数：{sPlayer}",
        )
    )


def handle_online_players(status: dict, messages):
    if players := status.get("players", {}).get("sample", []):
        sOnlinePlayer = " | ".join(player["name"] for player in players)
        messages.append("\n在线玩家：" + sOnlinePlayer)


def handle_modinfo(status: dict, messages):
    modinfo = status.get("modinfo")
    if modinfo and "FML" in modinfo.get("type", ""):
        messages.append("\n模组Api：Forge")


def handle_mods(status: dict, messages):
    if mods := status.get("modinfo", {}).get("modList") or status.get("forgeData", {}).get("mods"):
        messages.append("\nMod数：" + str(len(mods)) + " +")
        sMods = [f"{mod['modid']}@{mod['version']}" for mod in mods[:10]]
        if len(mods) > 10:
            sMods.append("......（仅显示前 10 个 mod）")
        messages.append("\n".join(sMods))


async def get_mcping(say: str):
    try:
        status = await asyncio.to_thread(get_server_status, say)
    except Exception as e:
        logger.exception(e)
        return [f"服务器信息获取失败\n{e}"]

    messages = [f"延迟：{status.get('ping', '')}ms\n"]

    await handle_favicon(status, messages)
    handle_description(status, messages)
    handle_version(status, messages)
    handle_online_players(status, messages)
    handle_modinfo(status, messages)
    handle_mods(status, messages)

    return messages
