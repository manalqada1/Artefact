"""Catch missing module-level imports after moving code between files.

This does not import Spark, Airflow, or storage clients, or start any services.
"""
import builtins
from pathlib import Path
import symtable
import unittest


class ModuleBindingTests(unittest.TestCase):
    def test_referenced_globals_are_bound(self):
        root = Path(__file__).resolve().parents[1] / 'src'
        built_in_names = set(dir(builtins)) | {
            '__name__', '__file__', '__package__', '__doc__',
        }
        problems = []
        for path in sorted(root.rglob('*.py')):
            table = symtable.symtable(path.read_text(encoding='utf-8'), str(path), 'exec')
            module_names = {
                symbol.get_name() for symbol in table.get_symbols()
                if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
            }

            def visit(scope):
                for symbol in scope.get_symbols():
                    if (symbol.is_global() and symbol.is_referenced()
                            and symbol.get_name() not in module_names | built_in_names):
                        problems.append(
                            f'{path.relative_to(root)}:{scope.get_name()}: {symbol.get_name()}'
                        )
                for child in scope.get_children():
                    visit(child)

            visit(table)
        self.assertEqual(problems, [], 'Unbound global names: ' + ', '.join(problems))
