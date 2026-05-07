from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from developer_assistant import state_store
from developer_assistant.hermes_plugins.dev_assist_escalation_policy.plugin import (
    pre_tool_call,
    _is_read_only,
    _is_within_catalog,
)
from developer_assistant.hermes_plugins.dev_assist_escalation_policy.rules import (
    evaluate_rules,
    ALL_RULES,
)


class TestReadOnlyBypass(unittest.TestCase):
    def test_read_file_bypasses(self):
        result = pre_tool_call("read_file", {"path": "/etc/passwd"})
        self.assertEqual(result["decision"], "allow")

    def test_list_files_bypasses(self):
        result = pre_tool_call("list_files", {"path": "."})
        self.assertEqual(result["decision"], "allow")

    def test_session_search_bypasses(self):
        result = pre_tool_call("session_search", {"query": "test"})
        self.assertEqual(result["decision"], "allow")

    def test_memory_add_own_bypasses(self):
        with patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"}):
            result = pre_tool_call(
                "memory_add",
                {"path": "/srv/devassist/runtimes/executor/.hermes/MEMORY.md", "content": "note"},
            )
            self.assertEqual(result["decision"], "allow")


class TestWithinCatalogBypass(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_within_catalog_model_bypasses_classifier(self):
        result = pre_tool_call(
            "tool_call",
            {"model": "accounts/fireworks/models/glm-5p1", "_llm_call": True},
            conn=self.conn,
        )
        self.assertEqual(result["decision"], "allow")

    def test_outside_catalog_model_fires_paid_rule(self):
        result = pre_tool_call(
            "tool_call",
            {"model": "accounts/fireworks/models/unknown-model", "_llm_call": True},
            conn=self.conn,
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("paid:llm_provider_outside_catalog", result["trigger_kind"])


class TestDeterministicRulesPositive(unittest.TestCase):
    def _check(self, rule_id, action_kind, action_args):
        result = evaluate_rules(action_kind, action_args)
        self.assertEqual(result, rule_id, f"Expected {rule_id} but got {result}")

    def test_gov_write_outside_zone(self):
        self._check("gov:write_outside_zone", "file_write", {"path": "src/unrelated.py", "allowed_files": ["src/allowed.py"]})

    def test_gov_delete_governance_artifact(self):
        self._check("gov:delete_governance_artifact", "file_delete", {"path": "docs/prd/PRD-001.md"})

    def test_gov_overwrite_approved_artifact(self):
        self._check("gov:overwrite_approved_artifact", "file_write", {
            "path": "docs/architecture/test.md",
            "old_content": "---\nstatus: approved\n---\nold text",
            "content": "---\nstatus: approved\n---\nnew text",
        })

    def test_gov_rename_artifact(self):
        self._check("gov:rename_artifact", "file_rename", {"old_path": "docs/architecture/test.md", "new_path": "docs/architecture/test2.md"})

    def test_git_force_push(self):
        self._check("git:force_push", "shell_command", {"command": "git push origin --force"})

    def test_git_force_with_lease_main_master(self):
        self._check("git:force_with_lease_main_master", "shell_command", {"command": "git push --force-with-lease origin main"})

    def test_git_hard_reset(self):
        self._check("git:hard_reset", "shell_command", {"command": "git reset --hard HEAD~1"})

    def test_git_branch_delete(self):
        self._check("git:branch_delete", "shell_command", {"command": "git branch -D feature-x"})

    def test_git_rebase_main_master(self):
        self._check("git:rebase_main_master", "shell_command", {"command": "git rebase origin/main"})

    def test_git_no_verify_commit_or_push(self):
        self._check("git:no_verify_commit_or_push", "shell_command", {"command": "git commit --no-verify -m test"})

    def test_state_drop_table(self):
        self._check("state:drop_table", "shell_command", {"command": "DROP TABLE work_items"})

    def test_state_drop_database(self):
        self._check("state:drop_database", "shell_command", {"command": "DROP DATABASE operational"})

    def test_state_truncate_or_delete_unbounded(self):
        self._check("state:truncate_or_delete_unbounded", "shell_command", {"command": "TRUNCATE work_items"})

    def test_state_alter_table_drop_column(self):
        self._check("state:alter_table_drop_column", "shell_command", {"command": "ALTER TABLE work_items DROP COLUMN result_json"})

    def test_state_downgrade_schema(self):
        self._check("state:downgrade_schema", "tool_call", {"content": "downgrade schema to v1", "sql": "downgrade schema"})

    def test_secret_rotate(self):
        self._check("secret:rotate", "file_write", {"path": "/srv/devassist/secrets/SELF-DEPLOY.env", "content": "GITHUB_TOKEN=ghp_newtoken"})

    def test_secret_revoke(self):
        self._check("secret:revoke", "shell_command", {"command": "revokeBotToken 123456"})

    def test_secret_write_to_repo(self):
        self._check("secret:write_to_repo", "file_write", {"content": "key=sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"})

    def test_secret_expose_in_log(self):
        self._check("secret:expose_in_log", "shell_command", {"output": "token=ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"})

    def test_net_open_inbound_port(self):
        self._check("net:open_inbound_port", "shell_command", {"command": "ufw allow 8080"})

    def test_net_webhook_mode_telegram(self):
        self._check("net:webhook_mode_telegram", "shell_command", {"command": "setWebhook https://example.com/hook"})

    def test_net_expose_endpoint(self):
        self._check("net:expose_endpoint", "shell_command", {"command": "ngrok http 8080"})

    def test_paid_new_recurring_service(self):
        self._check("paid:new_recurring_service", "shell_command", {"command": "pip install modal.com sdk"})

    def test_paid_llm_provider_outside_catalog(self):
        self._check("paid:llm_provider_outside_catalog", "tool_call", {"model": "gpt-4o"})

    def test_paid_cloud_resource_provision(self):
        self._check("paid:cloud_resource_provision", "shell_command", {"command": "aws ec2 run-instances --image-id ami-123"})

    def test_deploy_start_units_unprompted(self):
        self._check("deploy:start_units_unprompted", "shell_command", {"command": "systemctl start devassist.target"})

    def test_deploy_upgrade_activate_unprompted(self):
        self._check("deploy:upgrade_activate_unprompted", "shell_command", {"command": "upgrade-self.sh --activate"})

    def test_deploy_generated_project_live_run(self):
        self._check("deploy:generated_project_live_run", "shell_command", {"command": "live-run deploy prod"})

    def test_deploy_merge_pr(self):
        self._check("deploy:merge_pr", "shell_command", {"command": "gh pr merge 42"})

    def test_plugin_install_unallowed(self):
        self._check("plugin:install_unallowed", "shell_command", {"command": "hermes plugin install unknown-plugin"})

    def test_plugin_enable_project_local(self):
        self._check("plugin:enable_project_local", "file_write", {"content": "HERMES_ENABLE_PROJECT_PLUGINS=true"})

    def test_plugin_enable_marketplace_autoinstall(self):
        self._check("plugin:enable_marketplace_autoinstall", "shell_command", {"command": "config marketplace auto-install skill"})

    def test_plugin_agent_managed_skill_create(self):
        self._check("plugin:agent_managed_skill_create", "tool_call", {"tool": "skill_manage", "action": "create"})

    def test_scope_prd_status_to_approved(self):
        self._check("scope:prd_status_to_approved", "file_write", {
            "path": "docs/prd/PRD-001.md",
            "content": "---\nstatus: approved\n---",
            "old_content": "---\nstatus: draft\n---",
        })

    def test_scope_adr_status_to_approved(self):
        self._check("scope:adr_status_to_approved", "file_write", {
            "path": "docs/architecture/adr/ADR-001.md",
            "content": "---\nstatus: accepted\n---",
            "old_content": "---\nstatus: proposed\n---",
        })

    def test_scope_add_v01_commitment(self):
        self._check("scope:add_v01_commitment", "file_write", {
            "path": "docs/prd/PRD-001.md",
            "content": "---\n---\nLong content added here",
            "old_content": "---\n---\nShort",
        })

    def test_concept_replace_target_user(self):
        self._check("concept:replace_target_user", "file_write", {
            "path": "docs/prd/PRD-001.md",
            "content": "§ 2 Vision changed",
        })

    def test_concept_replace_tech_stack(self):
        self._check("concept:replace_tech_stack", "shell_command", {"command": "replace_hermes with something"})

    def test_concept_replace_runtime_target(self):
        self._check("concept:replace_runtime_target", "shell_command", {"command": "deploy_to_aws"})

    def test_concept_expose_private_endpoint(self):
        from developer_assistant.hermes_plugins.dev_assist_escalation_policy.rules import concept_expose_private_endpoint
        result = concept_expose_private_endpoint("shell_command", {"command": "ngrok http 3000"})
        self.assertEqual(result, "concept:expose_private_endpoint")


class TestDeterministicRulesNegative(unittest.TestCase):
    def _check_none(self, action_kind, action_args):
        result = evaluate_rules(action_kind, action_args)
        self.assertIsNone(result, f"Expected None but got {result}")

    def test_gov_write_outside_zone_in_zone(self):
        self._check_none("file_write", {"path": "src/allowed.py", "allowed_files": ["src/allowed.py"]})

    def test_gov_delete_non_governance(self):
        self._check_none("file_delete", {"path": "src/main.py"})

    def test_gov_overwrite_draft_artifact(self):
        self._check_none("file_write", {
            "path": "docs/architecture/test.md",
            "old_content": "---\nstatus: draft\n---\ntext",
            "content": "---\nstatus: draft\n---\nnew text",
        })

    def test_gov_rename_non_docs(self):
        self._check_none("file_rename", {"old_path": "src/foo.py", "new_path": "src/bar.py"})

    def test_git_normal_push(self):
        self._check_none("shell_command", {"command": "git push origin feature-x"})

    def test_git_soft_reset(self):
        self._check_none("shell_command", {"command": "git reset --soft HEAD~1"})

    def test_git_branch_list(self):
        self._check_none("shell_command", {"command": "git branch -a"})

    def test_git_normal_rebase(self):
        self._check_none("shell_command", {"command": "git rebase feature-x"})

    def test_git_normal_commit(self):
        self._check_none("shell_command", {"command": "git commit -m test"})

    def test_state_normal_query(self):
        self._check_none("shell_command", {"command": "SELECT * FROM work_items"})

    def test_state_insert(self):
        self._check_none("shell_command", {"command": "INSERT INTO work_items VALUES (1)"})

    def test_state_delete_with_where(self):
        self._check_none("shell_command", {"command": "DELETE FROM work_items WHERE id = 1"})

    def test_state_alter_add_column(self):
        self._check_none("shell_command", {"command": "ALTER TABLE work_items ADD COLUMN note TEXT"})

    def test_secret_read_env(self):
        self._check_none("shell_command", {"command": "echo $HOME"})

    def test_secret_write_non_secret_file(self):
        self._check_none("file_write", {"path": "src/main.py", "content": "print('hello')"})

    def test_net_normal_curl(self):
        self._check_none("shell_command", {"command": "curl https://api.example.com/data"})

    def test_paid_free_service(self):
        self._check_none("shell_command", {"command": "pip install requests"})

    def test_paid_catalog_model(self):
        self._check_none("tool_call", {"model": "accounts/fireworks/models/glm-5p1"})

    def test_deploy_normal_systemctl_status(self):
        self._check_none("shell_command", {"command": "systemctl status devassist.target"})

    def test_plugin_install_allowed_skill(self):
        self._check_none("shell_command", {"command": "pip install numpy"})

    def test_scope_write_non_prd(self):
        self._check_none("file_write", {"path": "src/main.py", "content": "new content"})

    def test_concept_normal_edit(self):
        self._check_none("file_write", {"path": "src/code.py", "content": "def foo(): pass"})

    def test_net_no_expose(self):
        self._check_none("shell_command", {"command": "ls -la"})


class TestFailClosed(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_rule_engine_exception_blocks(self):
        with patch(
            "developer_assistant.hermes_plugins.dev_assist_escalation_policy.plugin.evaluate_rules",
            side_effect=RuntimeError("boom"),
        ):
            result = pre_tool_call("shell_command", {"command": "rm -rf /"}, conn=self.conn)
            self.assertEqual(result["decision"], "blocked")
            self.assertEqual(result["trigger_kind"], "rule_engine_unavailable")

    def test_classifier_exception_blocks(self):
        with patch(
            "developer_assistant.hermes_plugins.dev_assist_escalation_policy.plugin.evaluate_rules",
            return_value=None,
        ), patch(
            "developer_assistant.hermes_plugins.dev_assist_escalation_policy.plugin.classify_concept_deviation",
            side_effect=RuntimeError("boom"),
        ):
            result = pre_tool_call("shell_command", {"command": "something"}, conn=self.conn)
            self.assertEqual(result["decision"], "blocked")
            self.assertEqual(result["trigger_kind"], "classifier_error")


class TestAdvisoryNarrative(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_advisory_timeout_narrative_null(self):
        def slow_dispatcher(prompt):
            raise TimeoutError("timed out")

        result = pre_tool_call(
            "shell_command",
            {"command": "git push --force origin main"},
            conn=self.conn,
            advisory_dispatcher=slow_dispatcher,
        )
        self.assertEqual(result["decision"], "blocked")

    def test_advisory_success_narrative(self):
        def good_dispatcher(prompt):
            return "Это действие было заблокировано"

        result = pre_tool_call(
            "shell_command",
            {"command": "git push --force origin main"},
            conn=self.conn,
            advisory_dispatcher=good_dispatcher,
        )
        self.assertEqual(result["decision"], "blocked")


class TestConceptClassifierCalledOnlyWhenNoRuleMatched(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_rule_match_skips_classifier(self):
        with patch(
            "developer_assistant.hermes_plugins.dev_assist_escalation_policy.plugin.classify_concept_deviation"
        ) as mock_classifier:
            pre_tool_call(
                "shell_command",
                {"command": "git push --force origin main"},
                conn=self.conn,
            )
            mock_classifier.assert_not_called()

    def test_no_rule_match_calls_classifier(self):
        with patch(
            "developer_assistant.hermes_plugins.dev_assist_escalation_policy.plugin.classify_concept_deviation",
            return_value=None,
        ) as mock_classifier:
            pre_tool_call(
                "shell_command",
                {"command": "python3 scripts/build.py"},
                conn=self.conn,
            )
            mock_classifier.assert_called_once()


class TestWithinCatalogStillFiresPaidRuleOutside(unittest.TestCase):
    def setUp(self):
        self.conn = state_store.open_store(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_outside_catalog_model_fires_paid_even_if_otherwise_safe(self):
        result = pre_tool_call(
            "tool_call",
            {"model": "gpt-4o", "_llm_call": True},
            conn=self.conn,
        )
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("paid:llm_provider_outside_catalog", result["trigger_kind"])


class TestRuleCount(unittest.TestCase):
    def test_all_40_rules_present(self):
        self.assertEqual(len(ALL_RULES), 40)


class TestMemoryToolBypass(unittest.TestCase):
    """Memory tools bypass ONLY for this runtime's own MEMORY.md."""

    def test_memory_add_own_memory_bypasses(self):
        with patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"}):
            result = pre_tool_call(
                "memory_add",
                {"path": "/srv/devassist/runtimes/executor/.hermes/MEMORY.md", "content": "note"},
            )
            self.assertEqual(result["decision"], "allow")

    def test_memory_replace_own_memory_bypasses(self):
        with patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"}):
            result = pre_tool_call(
                "memory_replace",
                {"path": "/srv/devassist/runtimes/executor/.hermes/MEMORY.md", "old": "x", "new": "y"},
            )
            self.assertEqual(result["decision"], "allow")

    def test_memory_remove_own_memory_bypasses(self):
        with patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"}):
            result = pre_tool_call(
                "memory_remove",
                {"path": "/srv/devassist/runtimes/executor/.hermes/MEMORY.md", "old": "x"},
            )
            self.assertEqual(result["decision"], "allow")

    def test_memory_add_other_runtime_does_not_bypass(self):
        with patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"}), \
             patch("developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier._anchor", None):
            result = pre_tool_call(
                "memory_add",
                {"path": "/srv/devassist/runtimes/orchestrator/.hermes/MEMORY.md", "content": "note"},
            )
            self.assertNotEqual(result["decision"], "allow")

    def test_memory_replace_other_runtime_does_not_bypass(self):
        with patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"}), \
             patch("developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier._anchor", None):
            result = pre_tool_call(
                "memory_replace",
                {"path": "/srv/devassist/runtimes/reviewer/.hermes/MEMORY.md", "old": "x", "new": "y"},
            )
            self.assertNotEqual(result["decision"], "allow")

    def test_memory_remove_other_runtime_does_not_bypass(self):
        with patch.dict(os.environ, {"HERMES_DEVASSIST_ROLE": "executor"}), \
             patch("developer_assistant.hermes_plugins.dev_assist_escalation_policy.concept_classifier._anchor", None):
            result = pre_tool_call(
                "memory_remove",
                {"path": "/srv/devassist/runtimes/planner/.hermes/MEMORY.md", "old": "x"},
            )
            self.assertNotEqual(result["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
