"""后置精炼钩子

在精炼流程之后，对提案标题进行格式校验与自动重写。
"""


def run(proposal: dict) -> dict:
    """后置精炼钩子入口。

    调用格式校验器校验并重写提案标题，更新提案的 title 与 auto_rewritten 字段。

    Args:
        proposal: 提案字典，需包含 title 字段。

    Returns:
        处理后的提案字典，title 已校验/重写，auto_rewritten 标识是否经过重写。
    """
    # 延迟导入避免循环依赖
    from backend.constraints import format_validator

    title = proposal.get("title", "")
    result = format_validator.validate_and_rewrite(title)

    # 更新提案字段
    proposal["title"] = result["title"]
    proposal["auto_rewritten"] = result["auto_rewritten"]

    return proposal
