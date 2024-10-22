import json
import shutil

from pathlib import Path
from typing import Dict, Tuple, Union

from gdtoolkit.parser import parser
from lark import Tree, Token

from .consts import DIR_SOURCE, DIR_TRANS

def extract_string(
    node: Tree, stmt: Tree = None, expr: Tree = None, func: str = ""
) -> Dict[Tuple, Dict]:
    result = {}
    if isinstance(node, Token):
        if "STRING" in node.type:
            text = node.value
            if expr is None:
                if node.type == "REGULAR_STRING":
                    if text == "\" \"":
                        range = (node.pos_in_stream, node.end_pos)
                    else:
                        range = (node.pos_in_stream + 1, node.end_pos - 1)
                elif node.type == "LONG_STRING":
                    range = (node.pos_in_stream + 3, node.end_pos - 3)
            else:
                # range = (expr.line, expr.column, expr.end_line, expr.end_column)
                range = (expr.meta.start_pos, expr.meta.end_pos)
            if stmt is None:
                context_range = (node.line, node.end_line)
            elif stmt == "no context":
                context_range = (node.line, node.end_line - 1)
            else:
                context_range = (stmt.line, stmt.end_line)
            if range[1] - range[0] <= 0:
                return {}
            return {range: {"range": range, "context_range": context_range, "func": func}}
        return {}
    if node.data == "getattr":
        call_name = node.children[-1].value
        if call_name in [
            "get_node",
            "get_node_or_null",
            "has",
            "Color",
            "preload",
            "load",
        ]:
            return {}
    elif node.data == "standalone_call" or node.data == "getattr_call":
        call_name = (
            node.children[0].value
            if node.data == "standalone_call"
            else node.children[0].children[-1].value
        )
        arg_num = (len(node.children) - 2) // 2
        if call_name in [
            "get_node",
            "get_node_or_null",
            "has",
            "Color",
            "preload",
            "load",
        ]:
            return {}
        elif call_name == "emit_signal":
            if arg_num <= 1:
                return {}
        elif call_name == "connect":
            if arg_num <= 3:
                return {}
    if "stmt" in node.data:
        in_stmt = node
    else:
        in_stmt = stmt
    if expr is not None:
        in_expr = expr
    elif node.data in ["arith_expr", "mdr_expr", "asgnmnt_expr"]:
        in_expr = node
    elif node.data == "array":
        if len(node.children) <= 18:
            in_expr = node
        else:
            # split when too long
            in_expr = None
            in_stmt = "no context"
    elif node.data == "subscr_expr":
        return {}
    else:
        in_expr = expr
    if node.data == "c_dict_element":
        # ignore key in dict
        children = node.children[1:]
    else:
        children = node.children
    if node.data == "func_def":
        in_func = node.children[0].children[0].value
    else:
        in_func = func
    for child in children:
        str_list = extract_string(child, stmt=in_stmt, expr=in_expr, func=in_func)
        for key, value in str_list.items():
            result[key] = value
    return result



def extract(source_path: Union[Path, str], result_path: Union[Path, str]):
    if isinstance(source_path, str):
        source_path = Path(source_path)
    if isinstance(result_path, str):
        result_path = Path(result_path)
        
    if result_path.exists():
        shutil.rmtree(result_path)
    result_path.mkdir(parents=True, exist_ok=True)

    for file in source_path.glob("**/*.gd"):
        with open(file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            code = "".join(lines)

        tree = parser.parse(code, gather_metadata=True)

        ranges = extract_string(tree)
        result = []

        for idx, item in enumerate(ranges.values()):
            range = item["range"]
            stmt_line = item["context_range"]
            func = item["func"]
            if len(range) == 2:
                original = code[range[0] : range[1]]
            elif len(range) == 4:
                if range[0] == range[2]:
                    original = lines[range[0] - 1][range[1] - 1 : range[3] - 1]
                else:
                    original = lines[range[0] - 1][range[1] - 1 :]
                    original += "".join(lines[range[0] : range[2] - 1])
                    original += lines[range[2] - 1][: range[3] - 1]
            context = "".join(lines[stmt_line[0] - 1 : stmt_line[1]])
            if func != "":
                context = f"Function Name: {func}\n{context}"
            result.append(
                {
                    "key": str(range),
                    "original": original.replace("\\n", "__NEWLINE__"),
                    "translation": "",
                    "stage": 0,
                    "context": context,
                }
            )
        if len(result) == 0:
            continue

        target_file: Path = result_path.joinpath(file.relative_to(source_path)).with_suffix(
            f"{file.suffix}.json"
        )
        target_folder: Path = target_file.parent
        if not target_folder.exists():
            target_folder.mkdir(parents=True)

        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    for file in source_path.glob("**/*.tscn"):
        with open(file, "r", encoding='utf-8') as f:
            code = f.readlines()

        result = []

        start_line = -1
        node_name = ""
        for idx, line in enumerate(code):
            new_node = (line.startswith('[node') or line.startswith('[connection')) and line.endswith(']\n')
            if start_line != -1 and (" = " in line or new_node):
                end_line = idx - 1

                result.append(
                    {
                        "key": str((start_line, end_line)),
                        "original": "".join(code[start_line : end_line + 1]),
                        "translation": "",
                        "stage": 0,
                        "context": node_name
                    }
                )

                start_line = -1
            if (
                "text = " in line
                or "Text = " in line
                or "Name = " in line
                or "Description = " in line
                or "tooltip = " in line
                or "title = " in line
            ):
                start_line = idx
            if new_node:
                node_name = line
        if start_line != -1:
            end_line = len(code) - 1
            result.append(
                {
                    "key": str((start_line, end_line)),
                    "original": "".join(code[start_line : end_line + 1]).replace("\\n","__NEWLINE__"),
                    "translation": "",
                    "stage": 0
                }
            )

        if len(result) == 0:
            continue

        target_file: Path = result_path.joinpath(file.relative_to(source_path)).with_suffix(
            f"{file.suffix}.json"
        )
        target_folder: Path = target_file.parent
        if not target_folder.exists():
            target_folder.mkdir(parents=True)

        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    extract(DIR_SOURCE, DIR_TRANS)
