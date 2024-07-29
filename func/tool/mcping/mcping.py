import asyncio
import base64
import contextlib
import json
import re
from io import BytesIO

import aiodns
from aiodns.error import DNSError
from avilla.core import Picture
from loguru import logger
from PIL import Image

from utils.message.picture import SelfPicture

from .statusping import StatusPing

resolver = aiodns.DNSResolver(loop=asyncio.get_event_loop(), nameservers=["223.5.5.5"])


async def srv_dns_resolver(host: str) -> tuple[str, int] | tuple[None, None]:
    with contextlib.suppress(DNSError):
        srv_records = await resolver.query(f"_minecraft._tcp.{host}", "SRV")
        host = srv_records[0].host
        port = srv_records[0].port
        return host, port
    return None, None


def ping_status(host: str, port: int | None = None) -> dict:
    status_ping = StatusPing(host, port or 25565)
    status = status_ping.get_status()
    status_str = json.dumps(status)
    status_str = re.sub(r"\\u00a7.", "", status_str)
    status: dict = json.loads(status_str)
    logger.debug(status)
    return status


async def get_server_status(say: str) -> dict:
    host, _, port = say.partition(":")
    if port is not None:
        return await asyncio.to_thread(ping_status, host, int(port))
    _host, _port = await srv_dns_resolver(host)
    if _host is None:
        return await asyncio.to_thread(ping_status, host, int(port))
    return await asyncio.to_thread(ping_status, _host, _port)


async def handle_favicon(status: dict, messages: list[str | Picture]) -> None:
    if favicon := status.get("favicon"):
        byte_data = base64.b64decode(f"{favicon[22:-1]}=")
        img = Image.open(BytesIO(byte_data)).convert("RGB")
        image = BytesIO()
        img.save(image, format="JPEG", quality=90)
        messages.append(await SelfPicture().from_data(image, "jpeg"))


def handle_description(status: dict, messages: list[str | Picture]) -> None:
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


def handle_version(status: dict, messages: list[str | Picture]) -> None:
    version_name = status.get("version", {}).get("name", "")
    s_name = ""
    s_packagever = ""
    if "Requires" in version_name:
        s_type = "Vanilla"
        s_ver = version_name
    elif "modpackData" in status:
        s_type = "Modpack"
        s_ver = version_name
        s_packagever = status["modpackData"]["version"]
        s_name = status["modpackData"]["name"]
    else:
        s_type, _, s_ver = version_name.rpartition(" ")
        s_type = s_type or "Vanilla（或未知）"

    s_dev_ver = str(status.get("version", {}).get("protocol", ""))
    s_player = f"{status.get('players', {}).get('online', '')} / {status.get('players', {}).get('max', '')}"

    messages.extend(
        (
            f"服务端：{s_type}\n",
            f"游戏版本：{s_ver}\n",
            f"整合包名称：{s_name}\n" if s_name else "",
            f"整合包版本：{s_packagever}\n" if s_packagever else "",
            f"协议版本：{s_dev_ver}\n",
            f"玩家数：{s_player}",
        )
    )


def handle_online_players(status: dict, messages: list[str | Picture]) -> None:
    if players := status.get("players", {}).get("sample", []):
        s_online_player = " | ".join(player["name"] for player in players)
        messages.append("\n在线玩家：" + s_online_player)


def handle_modinfo(status: dict, messages: list[str | Picture]) -> None:
    modinfo = status.get("modinfo")
    if modinfo and "FML" in modinfo.get("type", ""):
        messages.append("\n模组Api：Forge")


def handle_mods(status: dict, messages: list[str | Picture]) -> None:
    if mods := status.get("modinfo", {}).get("modList") or status.get("forgeData", {}).get("mods"):
        messages.append("\nMod数：" + str(len(mods)) + " +")
        s_mods = [f"{mod['modid']}@{mod['version']}" for mod in mods[:10]]
        if len(mods) > 10:
            s_mods.append("......（仅显示前 10 个 mod）")
        messages.append("\n".join(s_mods))


async def get_mcping(say: str) -> list[str | Picture]:
    try:
        status = await get_server_status(say)
    except Exception as e:
        return [f"服务器信息获取失败\n{type(e)}: {e}"]

    messages: list[str | Picture] = [f"延迟：{status.get('ping', '')}ms\n"]

    await handle_favicon(status, messages)
    handle_description(status, messages)
    handle_version(status, messages)
    handle_online_players(status, messages)
    handle_modinfo(status, messages)
    handle_mods(status, messages)

    return messages
