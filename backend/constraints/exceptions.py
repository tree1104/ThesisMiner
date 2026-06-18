"""约束工程自定义异常

定义论文生成流程中可能触发的各类约束违规异常，
涵盖学术伦理熔断、可行性不足、格式校验失败、文献基线不足等场景。
"""


class ConstraintError(Exception):
    """约束违规基类"""

    pass


class EthicsCircuitBreaker(ConstraintError):
    """学术伦理熔断：抄袭、伪造数据、违背科学规律"""

    pass


class InfeasibleError(ConstraintError):
    """可行性不足：实验周期超期、资源不可得"""

    pass


class FormatValidationError(ConstraintError):
    """格式校验失败：标题超长、含主动动词等"""

    pass


class LiteratureBaselineError(ConstraintError):
    """文献基线不足"""

    pass
