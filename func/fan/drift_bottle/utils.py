import kayaku
import nh3
from markdown_it.token import Token

from func.fan.drift_bottle.crud import DriftingBottle
from services import S3File
from utils.builder import AUserBuilder
from utils.config import BasicConfig
from utils.text2image import md_converter

basic_config = kayaku.create(BasicConfig)


async def bottle_md_builder(s3file: S3File, bottle: DriftingBottle) -> str:
    bottle_md = f"# 你成功捞到一个漂流瓶！\n\n### 漂流瓶编号：{bottle.bottle_id}"
    if not bottle.anonymous:
        bottle_user = await AUserBuilder.get_user(bottle.aid, "aid")
        if not bottle_user:
            msg = f"漂流瓶 {bottle.bottle_id} 的用户 {bottle.aid} 不存在"
            raise RuntimeError(msg)
        bottle_md += f"\n\n- 来自群：{bottle.group_id}"
        bottle_md += f"\n- 来自AID：{bottle.aid}" + (f"（{bottle_user.nickname}）" if bottle_user.nickname else "")
    bottle_score = await bottle.get_score()
    if bottle_score:
        bottle_md += f"\n- 漂流瓶当前评分：{bottle_score} 分"
    else:
        bottle_md += "\n- 漂流瓶当前没有评分"
    bottle_md += f"\n\n> 可发送 “@ABot bottle score {bottle.bottle_id} <分数>” 为这个漂流瓶评分"
    bottle_md += f"\n\n> 可发送 “@ABot bottle discuss {bottle.bottle_id} <评论>” 为这个漂流瓶评论"
    bottle_md += "\n\n---\n\n"
    if bottle.text:
        clear_text = nh3.clean_text(bottle.text)
        bottle_md += f"\n\n{clear_text}"
    if bottle.images:
        for i, image in enumerate(bottle.images):
            bottle_md += f"\n\n![漂流瓶图片{i}]({await s3file.get_presigned_url(image)})"
    return bottle_md


_md = md_converter.md


def transform_token(tok: Token) -> None:
    if tok.type != "image":
        return
    if str(tok.attrs.get("src", "")).startswith(
        f"{'https' if basic_config.s3file.secure else 'http'}://{basic_config.s3file.endpoint}/abot7f8befa44d10"
    ):
        return

    tok.type = "text"
    tok.content = f"![{tok.attrs['alt']}]({tok.attrs['src']})"
    tok.attrs = {}


def transform_tokens(toks: list[Token]) -> list[Token]:
    for tok in toks:
        transform_token(tok)
        if tok.children:
            transform_tokens(tok.children)

    return toks


def transform_markdown(text: str) -> str:
    tokens = transform_tokens(_md.parse(text))
    html = _md.renderer.render(tokens, _md.options, {})
    return f'<div class="markdown-body">{html}</div>'
