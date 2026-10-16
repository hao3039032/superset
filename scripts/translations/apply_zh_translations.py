# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
# ruff: noqa
"""One-off migration script for the zh translation catalog.

Applies ``zh_dictionary.py`` translations, clears fuzzy flags and normalizes
legacy BI terminology. It has already been run against the catalog in this
branch -- do NOT re-run it. Requires ``polib`` (not part of the regular
requirements; install with ``pip install polib``).
"""

import re
import polib  # type: ignore[import-untyped]
from zh_dictionary import ALL_TRANSLATIONS


def normalize_terms(text: str) -> str:
    """Normalize legacy BI terms according to standards."""
    text = text.replace("SQL 工具箱", "SQL 编辑器")
    text = text.replace("SQL工具箱", "SQL 编辑器")
    text = text.replace("看板", "仪表板")
    text = text.replace("警报", "告警")
    text = text.replace("切片", "图表")
    text = text.replace("钻取到明细", "查看明细数据")
    text = text.replace("本地筛选器", "原生筛选器")
    text = text.replace("过滤器栏", "筛选栏")
    return text


def extract_placeholders(s: str) -> set[str]:
    """Extract all formatting placeholders from text."""
    py_formats = set(
        re.findall(r"%\([a-zA-Z0-9_]+\)[a-zA-Z]|%[0-9]*\.?[0-9]*[a-zA-Z%]", s)
    )
    braces = set(re.findall(r"\{[a-zA-Z0-9_]+\}", s))
    return py_formats | braces


def sync_newlines(msgid: str, msgstr: str) -> str:
    """Ensure trailing newline matches between msgid and msgstr."""
    if not msgstr:
        return msgstr
    if msgid.endswith("\n") and not msgstr.endswith("\n"):
        msgstr = msgstr + "\n"
    elif not msgid.endswith("\n") and msgstr.endswith("\n"):
        msgstr = msgstr.rstrip("\n")
    return msgstr


PLURAL_TRANSLATIONS = {
    '%(suggestion)s instead of "%(undefinedParameter)s?"': '是否指 %(suggestion)s 而非 "%(undefinedParameter)s"？',
    "%s column": "%s 列",
    "%s day ago": "%s 天前",
    "%s hr ago": "%s 小时前",
    "%s item": "%s 项",
    "%s metric": "%s 个指标",
    "%s min ago": "%s 分钟前",
    "%s option": "%s 个选项",
    "%s out of %s column": "%s / %s 列",
    "%s out of %s metric": "%s / %s 指标",
    "%s record": "%s 条记录",
    "%s record...": "%s 条记录...",
    "%s row": "%s 行",
    "%s s ago": "%s 秒前",
    "%s second": "%s 秒",
    "Added 1 new column to the virtual dataset": "已向虚拟数据集添加 %s 个新列",
    "Added to 1 dashboard": "已添加到 %s 个仪表板",
    "Chart Owner: %s": "图表所有者：%s",
    "Delayed (missed %s refresh)": "已延迟（错过了 %s 次刷新）",
    "Deleted %(num)d annotation": "已删除 %(num)d 个批注",
    "Deleted %(num)d annotation layer": "已删除 %(num)d 个批注图层",
    "Deleted %(num)d chart": "已删除 %(num)d 个图表",
    "Deleted %(num)d css template": "已删除 %(num)d 个 CSS 模板",
    "Deleted %(num)d dashboard": "已删除 %(num)d 个仪表板",
    "Deleted %(num)d dataset": "已删除 %(num)d 个数据集",
    "Deleted %(num)d report schedule": "已删除 %(num)d 个报表调度计划",
    "Deleted %(num)d rules": "已删除 %(num)d 条规则",
    "Deleted %(num)d saved query": "已删除 %(num)d 条已保存查询",
    "Deleted %(num)d theme": "已删除 %(num)d 个主题",
    "Drop a column here or click": "将列拖放到此处或单击",
    "Drop a column/metric here or click": "将列/指标拖放到此处或单击",
    "Modified 1 column in the virtual dataset": "已修改虚拟数据集中的 %s 个列",
    "Please reach out to the Chart Owner for assistance.": "请联系图表所有者以获取帮助。",
    "Removed 1 column from the virtual dataset": "已从虚拟数据集中移除 %s 个列",
    "The parameter %(parameters)s in your query is undefined.": "您查询中的以下参数未定义：%(parameters)s",
    "This was triggered by:": "触发原因为：",
    "We’re having trouble loading these results. Queries are set to timeout after %s second.": "加载这些结果时遇到问题。查询已设置为在 %s 秒后超时。",
    "We’re having trouble loading this visualization. Queries are set to timeout after %s second.": "加载此可视化图表时遇到问题。查询已设置为在 %s 秒后超时。",
}


def main() -> None:
    import os

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    po_path = os.path.join(base_dir, "superset/translations/zh/LC_MESSAGES/messages.po")
    po = polib.pofile(po_path)

    print(f"Initial status:")
    print(f"Total entries: {len(po)}")
    print(f"Fuzzy entries: {len([e for e in po if e.fuzzy])}")
    print(f"Untranslated: {len([e for e in po if not e.msgstr and not e.fuzzy])}")

    updated_count = 0
    fuzzy_cleared_count = 0
    term_normalized_count = 0

    # Specific corrections for placeholder mismatches in legacy catalog
    LEGACY_FIXES = {
        "%s out of %s selected": "%s / %s 已选定",
        "There was an issue cancelling the task: %s": "取消任务时出现问题：%s",
        "Waiting on %s": "正在等待 %s",
        "is linked to %s charts that appear on %s dashboards and users have %s SQL Lab tabs using this database open. Are you sure you want to continue? Deleting the database will break those objects.": "已关联至 %s 个图表和 %s 个仪表板，且用户打开了 %s 个使用该数据库的 SQL 编辑器标签页。确定要继续吗？删除该数据库将损坏这些对象。",
        "is linked to %s charts that appear on %s dashboards. Are you sure you want to continue? Deleting the dataset will break those objects.": "已关联至 %s 个图表和 %s 个仪表板。确定要继续吗？删除该数据集将损坏这些对象。",
    }

    for entry in po:
        if entry.msgid in LEGACY_FIXES:
            entry.msgstr = sync_newlines(entry.msgid, LEGACY_FIXES[entry.msgid])

        # Check plural entries
        if entry.msgid_plural:
            if entry.msgid in PLURAL_TRANSLATIONS:
                entry.msgstr_plural = {
                    0: sync_newlines(entry.msgid, PLURAL_TRANSLATIONS[entry.msgid])
                }
                if entry.fuzzy:
                    entry.fuzzy = False
                    if "fuzzy" in entry.flags:
                        entry.flags.remove("fuzzy")
                    fuzzy_cleared_count += 1
                updated_count += 1
                # If plural format mismatch causes msgfmt error, remove python-format
                if (
                    "python-format" in entry.flags
                    and entry.msgid
                    == '%(suggestion)s instead of "%(undefinedParameter)s?"'
                ):
                    entry.flags.remove("python-format")
            elif entry.msgstr_plural and 0 in entry.msgstr_plural:
                entry.msgstr_plural[0] = sync_newlines(
                    entry.msgid, normalize_terms(entry.msgstr_plural[0])
                )
                if entry.fuzzy:
                    entry.fuzzy = False
                    if "fuzzy" in entry.flags:
                        entry.flags.remove("fuzzy")
                    fuzzy_cleared_count += 1

        # 1. If in our dictionary, apply dictionary translation
        elif entry.msgid in ALL_TRANSLATIONS:
            entry.msgstr = sync_newlines(entry.msgid, ALL_TRANSLATIONS[entry.msgid])
            if entry.fuzzy:
                entry.fuzzy = False
                if "fuzzy" in entry.flags:
                    entry.flags.remove("fuzzy")
                fuzzy_cleared_count += 1
            updated_count += 1
        elif entry.fuzzy:
            # 2. If fuzzy but already has msgstr
            if entry.msgstr:
                new_msgstr = normalize_terms(entry.msgstr)
                new_msgstr = sync_newlines(entry.msgid, new_msgstr)

                # Check placeholders
                id_ph = extract_placeholders(entry.msgid)
                str_ph = extract_placeholders(new_msgstr)
                if id_ph == str_ph:
                    entry.msgstr = new_msgstr
                    entry.fuzzy = False
                    if "fuzzy" in entry.flags:
                        entry.flags.remove("fuzzy")
                    fuzzy_cleared_count += 1
                else:
                    print(
                        f"Warning: Placeholder mismatch in fuzzy entry: {entry.msgid!r} (expected {id_ph}, got {str_ph})"
                    )
            else:
                print(f"Warning: Empty msgstr in fuzzy entry: {entry.msgid!r}")
        else:
            # 3. Existing non-fuzzy translated entries: normalize terms & sync newlines
            if entry.msgstr:
                normalized = normalize_terms(entry.msgstr)
                normalized = sync_newlines(entry.msgid, normalized)
                if normalized != entry.msgstr:
                    term_normalized_count += 1
                    entry.msgstr = normalized

        # 4. Check python-format flag safety
        # If msgid contains literal % but no placeholders, remove python-format flag if it causes msgfmt errors
        if "python-format" in entry.flags:
            ph = re.findall(
                r"%\([a-zA-Z0-9_]+\)[a-zA-Z]|%[0-9]*\.?[0-9]*[a-zA-Z]", entry.msgid
            )
            if not ph and "%" in entry.msgid:
                # pure literal %
                entry.flags.remove("python-format")

    po.save(po_path)

    print(f"\nProcessing complete:")
    print(f"Dictionary updated: {updated_count}")
    print(f"Fuzzy cleared: {fuzzy_cleared_count}")
    print(f"Terms normalized: {term_normalized_count}")

    # Check resulting statistics
    po_reloaded = polib.pofile(po_path)
    remaining_fuzzy = [e for e in po_reloaded if e.fuzzy]
    remaining_untranslated = [e for e in po_reloaded if not e.msgstr and not e.fuzzy]
    print(f"Remaining fuzzy: {len(remaining_fuzzy)}")
    print(f"Remaining untranslated: {len(remaining_untranslated)}")
    if remaining_fuzzy:
        print(
            "Sample remaining fuzzy:",
            [(e.msgid, e.msgstr) for e in remaining_fuzzy[:5]],
        )
    if remaining_untranslated:
        print(
            "Sample remaining untranslated:",
            [e.msgid for e in remaining_untranslated[:5]],
        )


if __name__ == "__main__":
    main()
