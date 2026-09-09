"""The pipeline can update a deployment before start_execution returns."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from api.routes import app_factory as route
from models.deployment import Deployment


class ExecutionRaceTest(unittest.TestCase):
    def test_pipeline_progress_survives_arn_persistence(self):
        deployment = Deployment(
            deployment_name='demo', template_id='app-factory-demo',
            iac_type='terraform', aws_account='123456789012',
            aws_region='us-east-1', s3_bucket='test-bucket',
        )
        stored = deployment.model_dump()
        table = Mock()
        table.put_item.side_effect = lambda **kw: (stored.clear(), stored.update(kw['Item']))

        def update(**kw):
            # Minimal SET-expression table emulator, preserving unrelated fields.
            for assignment in kw['UpdateExpression'].removeprefix('SET ').split(','):
                name, value = assignment.strip().split(' = ')
                stored[name] = kw['ExpressionAttributeValues'][value]
        table.update_item.side_effect = update
        service = Mock(table=table)
        service.create_deployment.return_value = deployment
        service._to_item.side_effect = lambda value: value.model_dump()
        submissions = Mock()
        submissions.get_item.return_value = {'Item': {'use_case_name': 'demo'}}

        def start(**kw):
            stored.update(status='building', build_id='test-build', updated_at='pipeline-time')
            return {'executionArn': 'test-execution'}
        pipeline = SimpleNamespace(state_machine_arn='test-machine', sfn_client=Mock())
        pipeline.sfn_client.start_execution.side_effect = start
        with patch.object(route, 'get_table', return_value=submissions), \
             patch.object(route, 'get_deploy_svc', return_value=service), \
             patch.object(route, 'get_pipeline_svc', return_value=pipeline), \
             patch.object(route.boto3, 'client', return_value=Mock()), \
             patch.object(route.os, 'walk', return_value=[]), \
             patch.object(route.zipfile.ZipFile, 'write'):
            response = asyncio.run(route.deploy_submission('test-submission'))
        self.assertEqual(stored['status'], 'building')
        self.assertEqual(stored['build_id'], 'test-build')
        self.assertEqual(stored['updated_at'], 'pipeline-time')
        self.assertEqual(stored['execution_arn'], 'test-execution')
        self.assertEqual(response.execution_arn, 'test-execution')


if __name__ == '__main__':
    unittest.main()
