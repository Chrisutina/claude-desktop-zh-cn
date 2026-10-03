import importlib.util
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_PATCHER = ROOT / "scripts" / "patch_claude_zh_cn.py"
WINDOWS_PATCHER = ROOT / "scripts" / "install_windows.ps1"

PROTECTED_SELECTORS = (
    '[data-testid="user-message"]',
    ".standard-markdown",
    ".progressive-markdown",
    '[data-testid="chat-input"]',
    '[data-testid="conway-composer-input"]',
    '[data-testid="conway-user-message"] .user-bubble',
    '[data-testid="conway-output-cell"]',
)

BROAD_SELECTORS = (
    "article",
    "[data-testid*=conversation]",
    "[data-testid*=message]",
    "[data-testid*=assistant]",
    "[data-testid*=tool]",
    "[data-testid*=artifact]",
    "[data-testid*=prompt]",
    "[data-testid*=composer]",
    "[class*=conversation]",
    "[class*=message]",
    "[class*=artifact]",
    "[class*=composer]",
)


def load_python_patcher():
    spec = importlib.util.spec_from_file_location("claude_zh_patcher", PYTHON_PATCHER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {PYTHON_PATCHER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_windows_dom_template() -> str:
    source = WINDOWS_PATCHER.read_text(encoding="utf-8-sig")
    function_start = source.index("function Get-OnlineDomTranslationScript")
    template_start = source.index("$template = @'", function_start) + len("$template = @'")
    template_end = source.index("\n'@", template_start)
    return source[template_start:template_end]


_WINDOWS_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _windows_added_month_rules(added_on_suffix: str) -> str:
    """Mirror the __ADDED_MONTH_RULES__ build in Get-OnlineDomTranslationScript.

    The placeholder sits inside a JS array literal as a bare element, so the
    replacement is raw comma-joined rule arrays -- neither quoted nor wrapped
    in [ ], which would nest them into one never-matching entry.
    """
    parts = []
    for index, month in enumerate(_WINDOWS_MONTH_NAMES):
        label = f"{index + 1}月$1日{added_on_suffix}"
        parts.append(
            '[/^added %s (\\d\\d?)(?:, \\d\\d\\d\\d)?$/,%s]'
            % (month, json.dumps(label, ensure_ascii=False, separators=(",", ":")))
        )
    for index, month in enumerate(_WINDOWS_MONTH_NAMES):
        for pattern, label in (
            (r"(\d\d?), (\d{4})", f"$2年{index + 1}月$1日"),
            (r"(\d\d?)", f"{index + 1}月$1日"),
        ):
            parts.append(
                f"[/^{month} {pattern}$/," +
                json.dumps(label, ensure_ascii=False, separators=(",", ":")) + "]"
            )
    return ",".join(parts)


def materialize_windows_dom_script(template: str) -> str:
    values = {
        "__LANGUAGE__": "zh-CN",
        "__MAPPING__": {"Settings": "设置", "deploy-command": "部署命令"},
        "__SELECTED_TEXT__": "已选择 $1 项",
        "__DELETE_SELECTED_TEXT__": "删除 $1 个所选项",
        "__UPDATED_MINUTE_TEXT__": "$1 分钟前更新",
        "__UPDATED_HOUR_TEXT__": "$1 小时前更新",
        "__UPDATED_DAY_TEXT__": "$1 天前更新",
        "__UPDATED_WEEK_TEXT__": "$1 周前更新",
        "__UPDATED_MONTH_TEXT__": "$1 个月前更新",
        "__UPDATED_YEAR_TEXT__": "$1 年前更新",
        "__AGO_SECOND__": "$1 秒前",
        "__AGO_MINUTE__": "$1 分钟前",
        "__AGO_HOUR__": "$1 小时前",
        "__AGO_DAY__": "$1 天前",
        "__AGO_WEEK__": "$1 周前",
        "__ADDED_MINUTE__": "$1 分钟前添加",
        "__ADDED_HOUR__": "$1 小时前添加",
        "__ADDED_DAY__": "$1 天前添加",
        "__ADDED_WEEK__": "$1 周前添加",
        "__ADDED_MONTH__": "$1 个月前添加",
        "__ADDED_YEAR__": "$1 年前添加",
        "__LEGACY_MEMORY_MIGRATION_TEXT__": "我们已迁移至新的记忆系统。如果你想导出旧版记忆，还剩 $1 天时间。",
        "__LEGACY_MEMORY_PREFIX_TEXT__": "我们已迁移至新的记忆系统。剩余 $1 天可",
        "__PAST_HOUR__": "过去 $1 小时",
        "__PAST_DAY__": "过去 $1 天",
        "__PAST_WEEK__": "过去 $1 周",
        "__PAST_MONTH__": "过去 $1 个月",
        "__PAST_YEAR__": "过去 $1 年",
        "__HIDE_SIDEBAR__": "隐藏侧边栏 ⌘ B",
        "__SHOW_SIDEBAR__": "显示侧边栏 ⌘ B",
        "__DELETE_ITEMS_PERMANENTLY__": "$1 项内容将被永久删除。此操作无法撤销。",
        "__DELETE_SELECTED_TITLE__": "删除所选项？",
        "__DELETE_CHAT_TITLE__": "删除聊天？",
        "__ORG_INFERENCE_TEXT__": "你正在通过组织的推理服务商（$1）使用 Claude。对话会发送到该服务商，而非 Anthropic，并受组织与该服务商签订的协议约束。",
    }
    script = template.replace(
        "__ADDED_MONTH_RULES__", _windows_added_month_rules("添加")
    )
    for placeholder, value in values.items():
        script = script.replace(
            placeholder, json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )
    # The patcher wraps its body in try/catch, so an unresolved placeholder
    # (an undefined identifier in JS) is swallowed silently and the generated
    # script becomes a no-op. Fail loudly instead of letting the template and
    # this substitution table drift apart again.
    leftover = sorted(set(re.findall(r"__[A-Z][A-Z0-9_]*__", script)))
    if leftover:
        raise AssertionError(
            f"template placeholders not substituted by the test harness: {leftover}"
        )
    return script


DOM_FIXTURE_PREFIX = r'''
const PROTECTED_SELECTORS = [
  '[data-testid="user-message"]',
  '.standard-markdown',
  '.progressive-markdown',
  '[data-testid="chat-input"]',
  '[data-testid="conway-composer-input"]',
  '[data-testid="conway-user-message"] .user-bubble',
  '[data-testid="conway-output-cell"]',
];

function selectorParts(selector) {
  return selector.split(',').map(part => part.trim()).filter(Boolean);
}

class TextNode {
  constructor(value) {
    this.nodeType = 3;
    this.nodeValue = value;
    this.parentElement = null;
  }
}

class Element {
  constructor(tagName = 'DIV', selectorTags = [], attributes = {}) {
    this.nodeType = 1;
    this.tagName = tagName.toUpperCase();
    this.selectorTags = new Set(selectorTags);
    this.attributes = {...attributes};
    this.children = [];
    this.parentElement = null;
    this.style = {};
    this.overwritten = false;
  }

  append(child) {
    child.parentElement = this;
    this.children.push(child);
    return child;
  }

  matchesSelector(part) {
    return this.selectorTags.has(part) || this.tagName.toLowerCase() === part;
  }

  closest(selector) {
    const parts = selectorParts(selector);
    for (let node = this; node; node = node.parentElement) {
      if (parts.some(part => node.matchesSelector(part))) return node;
    }
    return null;
  }

  querySelector(selector) {
    const parts = selectorParts(selector);
    const pending = [...this.children];
    while (pending.length) {
      const node = pending.shift();
      if (node.nodeType !== 1) continue;
      if (parts.some(part => node.matchesSelector(part))) return node;
      pending.unshift(...node.children);
    }
    return null;
  }

  get textContent() {
    return this.children.map(child =>
      child.nodeType === 3 ? child.nodeValue : child.textContent
    ).join('');
  }

  set textContent(value) {
    this.children = [];
    this.append(new TextNode(value));
    this.overwritten = true;
  }

  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name)
      ? this.attributes[name]
      : null;
  }

  setAttribute(name, value) {
    this.attributes[name] = value;
  }

  matches(selector) {
    return selector === 'input[type=button],input[type=submit]' &&
      (this.selectorTags.has('input[type=button]') ||
       this.selectorTags.has('input[type=submit]'));
  }

  getBoundingClientRect() {
    return {left: 0, top: 0};
  }
}

function collectTextNodes(node, result = []) {
  if (node.nodeType === 3) {
    result.push(node);
    return result;
  }
  for (const child of node.children) collectTextNodes(child, result);
  return result;
}

function textElement(text, selectorTags = [], tagName = 'DIV') {
  const element = new Element(tagName, selectorTags);
  element.append(new TextNode(text));
  return element;
}

const body = new Element('BODY');
const protectedContainers = PROTECTED_SELECTORS.map(selector =>
  body.append(textElement('Settings', [selector]))
);
body.append(new TextNode(' '));
const codeOwner = body.append(textElement('Settings', ['code'], 'CODE'));
const editableOwner = body.append(textElement('Settings', ['[contenteditable]']))
const slashOwner = body.append(textElement('deploy-command'));
const ordinaryUi = body.append(textElement('Settings'));

const ordinaryDialog = new Element('DIV');
ordinaryDialog.append(textElement('Set', [], 'SPAN'));
ordinaryDialog.append(textElement('tings', [], 'SPAN'));
body.append(ordinaryDialog);

const protectedDialog = new Element('DIV');
const protectedDialogChild = protectedDialog.append(
  textElement('Set', ['.standard-markdown'], 'SPAN')
);
protectedDialog.append(textElement('tings', [], 'SPAN'));
body.append(protectedDialog);

const ordinaryAttribute = new Element('BUTTON', [], {'aria-label': 'Settings'});
body.append(ordinaryAttribute);
const protectedAttributeOwner = new Element('DIV', ['.standard-markdown']);
const protectedAttribute = protectedAttributeOwner.append(
  new Element('BUTTON', [], {'aria-label': 'Settings'})
);
body.append(protectedAttributeOwner);

const ordinaryAnchor = body.append(textElement('Claude', [], 'A'));
const protectedAnchor = new Element('A');
protectedAnchor.append(textElement('Claude', ['.standard-markdown'], 'SPAN'));
body.append(protectedAnchor);

const interactiveDialog = new Element('DIV');
interactiveDialog.append(textElement('Set', [], 'SPAN'));
const interactiveLink = interactiveDialog.append(textElement('tings', [], 'A'));
body.append(interactiveDialog);

const dialogCandidates = [ordinaryDialog, protectedDialog, interactiveDialog];
const attributeCandidates = [ordinaryAttribute, protectedAttribute];
const anchorCandidates = [ordinaryAnchor, protectedAnchor];

globalThis.NodeFilter = {
  SHOW_TEXT: 4,
  FILTER_ACCEPT: 1,
  FILTER_REJECT: 2,
};
globalThis.window = globalThis;
globalThis.localStorage = {setItem() {}, getItem() { return null; }};
globalThis.MutationObserver = class {
  constructor(callback) { this.callback = callback; }
  observe() {}
};
globalThis.document = {
  body,
  documentElement: body,
  createTreeWalker(root, _whatToShow, filter) {
    const nodes = collectTextNodes(root);
    let index = 0;
    return {
      nextNode() {
        while (index < nodes.length) {
          const node = nodes[index++];
          if (!filter || filter.acceptNode(node) === NodeFilter.FILTER_ACCEPT) {
            return node;
          }
        }
        return null;
      },
    };
  },
  querySelectorAll(selector) {
    if (selector === '[role=dialog] p,[role=dialog] div,[role=dialog] span') {
      return dialogCandidates;
    }
    if (selector === '[aria-label],[title],[placeholder],input,textarea') {
      return attributeCandidates;
    }
    if (selector === 'a') return anchorCandidates;
    if (selector === 'div,fieldset') return [];
    return [];
  },
};
'''


DOM_FIXTURE_SUFFIX = r'''
const result = {
  protectedSelectors: protectedContainers.map(element => element.textContent),
  code: codeOwner.textContent,
  contenteditable: editableOwner.textContent,
  slash: slashOwner.textContent,
  ordinaryUi: ordinaryUi.textContent,
  ordinaryDialog: ordinaryDialog.textContent,
  ordinaryDialogOverwritten: ordinaryDialog.overwritten,
  protectedDialog: protectedDialog.textContent,
  protectedDialogOverwritten: protectedDialog.overwritten,
  protectedDialogChildren: protectedDialog.children.length,
  protectedDialogChildPreserved: protectedDialogChild.parentElement === protectedDialog,
  interactiveDialog: interactiveDialog.textContent,
  interactiveDialogOverwritten: interactiveDialog.overwritten,
  interactiveDialogChildren: interactiveDialog.children.length,
  interactiveLinkPreserved: interactiveDialog.children.includes(interactiveLink),
  ordinaryAttribute: ordinaryAttribute.getAttribute('aria-label'),
  protectedAttribute: protectedAttribute.getAttribute('aria-label'),
  ordinaryAnchorHidden: ordinaryAnchor.style.visibility,
  protectedAnchorHidden: protectedAnchor.style.visibility || null,
};
process.stdout.write(JSON.stringify(result));
'''


def run_dom_fixture(script: str, suffix: str = DOM_FIXTURE_SUFFIX) -> dict:
    completed = subprocess.run(
        ["node"],
        input=DOM_FIXTURE_PREFIX + "\n" + script + "\n" + suffix,
        text=True,
        # Node always emits UTF-8. Without an explicit encoding, text=True decodes
        # with the host locale codec (cp936 on Chinese Windows), which mangles any
        # non-ASCII assertion value into mojibake and fails the test spuriously.
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"Node fixture failed:\n{completed.stderr}")
    return json.loads(completed.stdout)


class DomTranslationGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.python_script = load_python_patcher().build_online_dom_translation_script(
            "zh-CN", {"Settings": "设置", "deploy-command": "部署命令"}
        )
        cls.windows_script = extract_windows_dom_template()
        cls.materialized_windows_script = materialize_windows_dom_script(
            cls.windows_script
        )

    def assert_common_guard_contract(self, script: str):
        for selector in PROTECTED_SELECTORS:
            self.assertEqual(script.count(selector), 1, selector)
        for selector in BROAD_SELECTORS:
            self.assertNotIn(selector, script)

        self.assertIn(
            "function Q(n){const e=n.nodeType===1?n:n.parentElement;"
            "return !!(e&&e.closest(P))}",
            script,
        )
        self.assertIn(
            "function H(n){return Q(n)||!!(n&&n.nodeType===1&&n.querySelector(P))}",
            script,
        )
        self.assertIn("p.closest('[contenteditable],'+C)||Q(n)||K(n)", script)
        self.assertIn(
            'e.closest("button,[contenteditable],"+C)||H(e)||K(e)', script
        )
        self.assertIn("e.closest(C)||Q(e)||K(e)", script)
        self.assertIn(
            'document.querySelectorAll("a").forEach(e=>{try{if(H(e))return;',
            script,
        )

        self.assertIn("pre,code,kbd,samp,var", script)
        self.assertIn("[data-testid*=code]", script)
        self.assertIn(".cm-editor,.monaco-editor,.hljs", script)
        self.assertIn("Custom command|Slash command", script)

    def assert_original_translation_paths(self, script: str):
        self.assertIn("if(M[n])return M[n]", script)
        self.assertIn("document.createTreeWalker(b,NodeFilter.SHOW_TEXT", script)
        self.assertIn(
            'document.querySelectorAll("[role=dialog] p,[role=dialog] div,'
            '[role=dialog] span")',
            script,
        )
        self.assertIn(
            'document.querySelectorAll("[aria-label],[title],[placeholder],input,textarea")',
            script,
        )
        self.assertIn("e.setAttribute(a,t)", script)
        self.assertIn('txt==="Claude"', script)
        self.assertIn("new MutationObserver", script)

    def test_python_generator_guards_every_existing_write_path(self):
        script = self.python_script
        self.assert_common_guard_contract(script)
        self.assert_original_translation_paths(script)
        self.assertIn(
            'document.querySelectorAll("div,fieldset").forEach(e=>{try{if(Q(e))return;',
            script,
        )
        self.assertIn("if(!Q(n)&&/^[SMTWF]$/.test", script)

    def test_windows_generator_matches_the_content_safety_contract(self):
        script = self.windows_script
        self.assert_common_guard_contract(script)
        self.assert_original_translation_paths(script)

    def assert_behavior_fixture(self, script: str):
        result = run_dom_fixture(script)
        self.assertEqual(result["protectedSelectors"], ["Settings"] * 7)
        self.assertEqual(result["code"], "Settings")
        self.assertEqual(result["contenteditable"], "Settings")
        self.assertEqual(result["slash"], "deploy-command")
        self.assertEqual(result["ordinaryUi"], "设置")

        self.assertEqual(result["ordinaryDialog"], "设置")
        self.assertTrue(result["ordinaryDialogOverwritten"])
        self.assertEqual(result["protectedDialog"], "Settings")
        self.assertFalse(result["protectedDialogOverwritten"])
        self.assertEqual(result["protectedDialogChildren"], 2)
        self.assertTrue(result["protectedDialogChildPreserved"])

        self.assertEqual(result["ordinaryAttribute"], "设置")
        self.assertEqual(result["protectedAttribute"], "Settings")
        self.assertEqual(result["ordinaryAnchorHidden"], "hidden")
        self.assertIsNone(result["protectedAnchorHidden"])

    def test_python_generated_script_preserves_protected_dom_content(self):
        self.assert_behavior_fixture(self.python_script)

    def test_windows_generated_script_preserves_protected_dom_content(self):
        self.assert_behavior_fixture(self.materialized_windows_script)


    def test_windows_dialog_translation_preserves_interactive_children(self):
        result = run_dom_fixture(self.materialized_windows_script)
        self.assertEqual(result["interactiveDialog"], "Settings")
        self.assertFalse(result["interactiveDialogOverwritten"])
        self.assertEqual(result["interactiveDialogChildren"], 2)
        self.assertTrue(result["interactiveLinkPreserved"])

    def test_windows_usage_and_site_permission_dynamic_values(self):
        expected = {
            "Hide sidebar Ctrl+B": "隐藏侧边栏 Ctrl+B",
            "Show sidebar Ctrl B": "显示侧边栏 Ctrl+B",
            "Hide sidebar ⌘B": "隐藏侧边栏 ⌘ B",
            "Show sidebar ⌘ B": "显示侧边栏 ⌘ B",
            "0% used": "已使用 0%",
            "55% used": "已使用 55%",
            "12.5% used": "已使用 12.5%",
            "Up to 30% off": "最高优惠 30%",
            "Up to 12.5% off": "最高优惠 12.5%",
            "Resets Sunday 1:00 PM": "周日 13:00 重置",
            "Resets Monday 9:30 AM": "周一 09:30 重置",
            "Resets Sunday 12:00 AM": "周日 00:00 重置",
            "Resets Sunday 12:00 PM": "周日 12:00 重置",
            "RESETS SUNDAY 1:00 PM": "周日 13:00 重置",
            "Resets Sunday 13:00": "周日 13:00 重置",
            "Resets Tue at 18:45": "周二 18:45 重置",
            "Resets tomorrow at 1:00 PM": "明天 13:00 重置",
            "Resets today 9:30 AM": "今天 09:30 重置",
            "Expires Oct 23": "10月23日到期",
            "Expires Oct 23, 2026": "2026年10月23日到期",
            "EXPIRES OCT 23": "10月23日到期",
            "Expires February 9": "2月9日到期",
            "Resets in 2h 15m": "2 小时 15 分钟后重置",
            "Resets in 2 hr 15 min": "2 小时 15 分钟后重置",
            "Resets in 3 hours": "3 小时后重置",
            "Resets in 30 min": "30 分钟后重置",
            "5-hour reset": "5 小时额度重置",
            "Domain 3": "域名 3",
            "Remove domain 3": "移除域名 3",
            "Choose whether Another product works on all sites by default":
                "选择是否默认允许 Another product 在所有网站上操作",
            "added Jan 9": "1月9日添加",
            "Oct 3, 2026": "2026年10月3日",
            "Delete selected?": "删除所选项？",
            "Past 24 hours": "过去 24 小时",
            "Low": None, "Medium": None, "High": None,
            "Extra": None, "Max": None, "Effort": None,
        }
        # Expose only the generated translator to the fixture; product code is unchanged.
        script = self.materialized_windows_script.replace(
            "const X=", "globalThis.translateForTest=R;const X=", 1
        )
        suffix = (
            "const samples=" + json.dumps(list(expected), ensure_ascii=False) + ";"
            "process.stdout.write(JSON.stringify(Object.fromEntries("
            "samples.map(s=>[s,translateForTest(s)??null]))));"
        )
        self.assertEqual(run_dom_fixture(script, suffix), expected)


if __name__ == "__main__":
    unittest.main()
