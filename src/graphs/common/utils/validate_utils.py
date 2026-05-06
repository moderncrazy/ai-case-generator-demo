from src.enums.review_optimization_plan_result import ReviewOptimizationPlanResult
from src.enums.pm_review_optimization_doc_result import PMReviewOptimizationDocResult
from src.enums.filtrate_optimization_doc_review_issue_result import FiltrateOptimizationDocReviewIssueResult
from src.graphs.common.schemas.output_schemas import (
    ReviewOptimizationPlanOutput,
    PMReviewOptimizationDocOutput,
    FiltrateOptimizationDocReviewIssueOutput)


def validate_review_optimization_plan_output_to_str(output: ReviewOptimizationPlanOutput) -> str:
    error_message = ""
    if not output.issues:
        match output.result:
            case ReviewOptimizationPlanResult.REVISE:
                error_message = "审核结果为：revise 时，issues 不能为空"
            case ReviewOptimizationPlanResult.ASK_QUESTION:
                error_message = "审核结果为：ask_question 时，issues 不能为空"
    return error_message


def validate_pm_review_optimization_doc_output_to_str(output: PMReviewOptimizationDocOutput) -> str:
    error_message = ""
    match output.result:
        case PMReviewOptimizationDocResult.REVISE:
            if not output.review_issues:
                error_message = "审核结果为：revise 时，review_issues 不能为空"
        case PMReviewOptimizationDocResult.GROUP_MEMBER_REVIEW:
            if not output.review_roles:
                error_message = "审核结果为：group_member_review 时，review_roles 不能为空"
    return error_message


def validate_filtrate_optimization_doc_review_issue_output_to_str(
        output: FiltrateOptimizationDocReviewIssueOutput) -> str:
    error_message = ""
    match output.result:
        case FiltrateOptimizationDocReviewIssueResult.REVISE:
            if not output.review_issues:
                error_message = "审核结果为：revise 时，review_issues 不能为空"
    return error_message
