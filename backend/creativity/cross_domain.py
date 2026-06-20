"""跨域联想与趋势嫁接模块

通过将成熟领域的方法嫁接至未解问题，或利用近期高频术语进行语义组合，
生成跨学科创新候选。
"""


def cross_domain_association(domain_a: str, domain_b: str) -> dict:
    """将领域 A 的成熟方法嫁接至领域 B 的未解问题。

    Args:
        domain_a: 提供成熟方法的领域。
        domain_b: 存在未解问题的领域。

    Returns:
        包含 inspiration_source、direction、suggestion、prompt 字段的候选字典。
    """
    return {
        "inspiration_source": "cross_domain",
        "direction": f"{domain_a}方法→{domain_b}问题",
        "suggestion": f"将{domain_a}的成熟方法嫁接至{domain_b}的未解问题",
        "prompt": f"将{domain_a}的成熟方法嫁接至{domain_b}的未解问题",
    }


def trend_grafting(keywords: list[str]) -> dict:
    """利用近期高频术语进行语义组合。

    Args:
        keywords: 近期高频术语列表。

    Returns:
        包含 inspiration_source、direction、suggestion、prompt 字段的候选字典。
    """
    return {
        "inspiration_source": "trend_graft",
        "direction": " + ".join(keywords),
        "suggestion": f"基于近期高频术语{keywords}的语义组合",
        "prompt": f"利用{keywords}等近期高频术语进行语义组合",
    }
