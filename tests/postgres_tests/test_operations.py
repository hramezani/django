import unittest

from migrations.test_base import OperationTestBase

from django.db import NotSupportedError, connection
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import ProjectState
from django.db.models import Index
from django.test import modify_settings, override_settings

try:
    from django.contrib.postgres.operations import (
        AddIndexConcurrently, RemoveIndexConcurrently,
        HStoreExtension,
    )
    from django.contrib.postgres.indexes import BrinIndex, BTreeIndex
except ImportError:
    pass


@unittest.skipUnless(connection.vendor == 'postgresql', 'PostgreSQL specific tests.')
@modify_settings(INSTALLED_APPS={'append': 'migrations'})
class AddIndexConcurrentlyTests(OperationTestBase):
    app_label = 'test_add_concurrently'

    def test_requires_atomic_false(self):
        project_state = self.set_up_test_model(self.app_label)
        new_state = project_state.clone()
        operation = AddIndexConcurrently(
            'Pony',
            Index(fields=['pink'], name='pony_pink_idx'),
        )
        msg = (
            'The AddIndexConcurrently operation cannot be executed inside '
            'a transaction (set atomic = False on the migration).'
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with connection.schema_editor(atomic=True) as editor:
                operation.database_forwards(self.app_label, editor, project_state, new_state)

    def test_add(self):
        project_state = self.set_up_test_model(self.app_label, index=False)
        table_name = '%s_pony' % self.app_label
        index = Index(fields=['pink'], name='pony_pink_idx')
        new_state = project_state.clone()
        operation = AddIndexConcurrently('Pony', index)
        self.assertEqual(
            operation.describe(),
            'Concurrently create index pony_pink_idx on field(s) pink of '
            'model Pony'
        )
        operation.state_forwards(self.app_label, new_state)
        self.assertEqual(len(new_state.models[self.app_label, 'pony'].options['indexes']), 1)
        self.assertIndexNotExists(table_name, ['pink'])
        # Add index.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(self.app_label, editor, project_state, new_state)
        self.assertIndexExists(table_name, ['pink'])
        # Reversal.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_backwards(self.app_label, editor, new_state, project_state)
        self.assertIndexNotExists(table_name, ['pink'])
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, 'AddIndexConcurrently')
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {'model_name': 'Pony', 'index': index})

    def test_add_other_index_type(self):
        project_state = self.set_up_test_model(self.app_label, index=False)
        table_name = '%s_pony' % self.app_label
        new_state = project_state.clone()
        operation = AddIndexConcurrently(
            'Pony',
            BrinIndex(fields=['pink'], name='pony_pink_brin_idx'),
        )
        self.assertIndexNotExists(table_name, ['pink'])
        # Add index.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(self.app_label, editor, project_state, new_state)
        self.assertIndexExists(table_name, ['pink'], index_type='brin')
        # Reversal.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_backwards(self.app_label, editor, new_state, project_state)
        self.assertIndexNotExists(table_name, ['pink'])

    def test_add_with_options(self):
        project_state = self.set_up_test_model(self.app_label, index=False)
        table_name = '%s_pony' % self.app_label
        new_state = project_state.clone()
        index = BTreeIndex(fields=['pink'], name='pony_pink_btree_idx', fillfactor=70)
        operation = AddIndexConcurrently('Pony', index)
        self.assertIndexNotExists(table_name, ['pink'])
        # Add index.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(self.app_label, editor, project_state, new_state)
        self.assertIndexExists(table_name, ['pink'], index_type='btree')
        # Reversal.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_backwards(self.app_label, editor, new_state, project_state)
        self.assertIndexNotExists(table_name, ['pink'])


@unittest.skipUnless(connection.vendor == 'postgresql', 'PostgreSQL specific tests.')
@modify_settings(INSTALLED_APPS={'append': 'migrations'})
class RemoveIndexConcurrentlyTests(OperationTestBase):
    app_label = 'test_rm_concurrently'

    def test_requires_atomic_false(self):
        project_state = self.set_up_test_model(self.app_label, index=True)
        new_state = project_state.clone()
        operation = RemoveIndexConcurrently('Pony', 'pony_pink_idx')
        msg = (
            'The RemoveIndexConcurrently operation cannot be executed inside '
            'a transaction (set atomic = False on the migration).'
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with connection.schema_editor(atomic=True) as editor:
                operation.database_forwards(self.app_label, editor, project_state, new_state)

    def test_remove(self):
        project_state = self.set_up_test_model(self.app_label, index=True)
        table_name = '%s_pony' % self.app_label
        self.assertTableExists(table_name)
        new_state = project_state.clone()
        operation = RemoveIndexConcurrently('Pony', 'pony_pink_idx')
        self.assertEqual(
            operation.describe(),
            'Concurrently remove index pony_pink_idx from Pony',
        )
        operation.state_forwards(self.app_label, new_state)
        self.assertEqual(len(new_state.models[self.app_label, 'pony'].options['indexes']), 0)
        self.assertIndexExists(table_name, ['pink'])
        # Remove index.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_forwards(self.app_label, editor, project_state, new_state)
        self.assertIndexNotExists(table_name, ['pink'])
        # Reversal.
        with connection.schema_editor(atomic=False) as editor:
            operation.database_backwards(self.app_label, editor, new_state, project_state)
        self.assertIndexExists(table_name, ['pink'])
        # Deconstruction.
        name, args, kwargs = operation.deconstruct()
        self.assertEqual(name, 'RemoveIndexConcurrently')
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {'model_name': 'Pony', 'name': 'pony_pink_idx'})


@unittest.skipUnless(connection.vendor == 'postgresql', 'PostgreSQL specific tests.')
@modify_settings(INSTALLED_APPS={'append': 'migrations'})
class ExtensionMigrationTests(OperationTestBase):
    app_label = 'test_extention_migration'

    def _database_move(self, operation, direction):
        project_state = ProjectState()
        new_state = project_state.clone()
        with connection.schema_editor() as editor:
            if direction == 'forwards':
                operation.database_forwards(self.app_label, editor, project_state, new_state)
            elif direction == 'backwards':
                operation.database_backwards(self.app_label, editor, project_state, new_state)

    def test_extention_migration(self):
        class TestRouter:
            def allow_migrate(self, db, app_label, **hints):
                return False

        tests = (
            ([], 'forwards', 'CREATE EXTENSION', 1),
            ([TestRouter()], 'forwards', 'CREATE EXTENSION', 0),
            ([], 'backwards', 'DROP EXTENSION', 1),
            ([TestRouter()], 'backwards', 'DROP EXTENSION', 0),
        )
        operation = HStoreExtension()
        for routers, direction, command, call_count in tests:
            with override_settings(DATABASE_ROUTERS=routers):
                with unittest.mock.patch.object(
                    BaseDatabaseSchemaEditor,
                    'execute'
                ) as execute:
                    self._database_move(operation, direction)
                    create_extension_count = len(
                        [call for call in execute.mock_calls if command in str(call)]
                    )
                    self.assertEqual(create_extension_count, call_count)
