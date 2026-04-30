from src.graphs.common.schemas import StateTestCase
from src.services.business.redis_service import redis_service
from src.repositories.test_case_repository import test_case_repository, TestCaseBulkUpdate


class TestCaseService:
    """测试用例服务"""

    def __init__(self):
        self.repository = test_case_repository

    async def bulk_update_by_state_test_cases(self, project_id: str, test_cases: list[StateTestCase]):
        """批量更新测试用例

        根据状态数据批量更新项目的测试用例信息。

        Args:
            project_id: 项目 ID
            test_cases: 状态中的 test_cases 列表
        """
        await self.repository.bulk_update(project_id, [TestCaseBulkUpdate(**item) for item in test_cases])
        await redis_service.delete_project_basic_info_cache(project_id)


test_case_service = TestCaseService()
