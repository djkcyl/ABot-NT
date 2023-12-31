from models.saya import FuncType


def build_metadata(
    func_type: FuncType,
    name: str,
    version: str,
    description: str,
    cmd_prefix: str | None = None,
    usage: list[str] | None = None,
    options: list[dict[str, str]] | None = None,
    example: list[dict[str, str]] | None = None,
    tips: list[str] | None = None,
    *,
    can_be_disabled: bool = True,
    default_enable: bool = True,
    hidden: bool = False,
    maintain: bool = False,
) -> dict[str, str | list[dict[str, str]] | list[str] | bool]:

    cmd_prefix = "" if cmd_prefix is None else cmd_prefix
    usage = [] if usage is None else [s.replace("<", "&lt;").replace(">", "&gt;") for s in usage]
    tips = [] if tips is None else [s.replace("<", "&lt;").replace(">", "&gt;") for s in tips]
    if options is None:
        options = []
    else:
        options = [{k: v.replace("<", "&lt;").replace(">", "&gt;") for k, v in d.items()} for d in options]
    if example is None:
        example = []
    else:
        example = [{k: v.replace("<", "&lt;").replace(">", "&gt;") for k, v in d.items()} for d in example]
    return {
        "func_type": func_type,
        "name": name,
        "version": version,
        "description": description,
        "cmd_prefix": cmd_prefix,
        "usage": usage,
        "options": options,
        "example": example,
        "tips": tips,
        "can_be_disabled": can_be_disabled,
        "default_enable": default_enable,
        "hidden": hidden,
        "maintain": maintain,
    }
