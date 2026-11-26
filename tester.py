#!/usr/bin/env python3
"""Tester for Growing Code (42 - Python Module 00).

Put the `tester/` folder at the root of the project (next to ex0/, ex1/...)
then run `make all` or `make ex3` from inside it.
"""

import ast
import builtins
import importlib.util
import io
import signal
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

OK = f"{GREEN}[OK]{RESET}"
KO = f"{RED}[KO]{RESET}"
SKIP = f"{YELLOW}[--]{RESET}"

stats = {"ok": 0, "ko": 0}
MAX_DETAILED_KO = 3  # per exercise, to avoid flooding the terminal
ko_in_exercise = [0]


# --------------------------------------------------------------------------- #
#  Display                                                                    #
# --------------------------------------------------------------------------- #

def report_ok(label):
    stats["ok"] += 1
    print(f"  {OK} {label}")


def report_ko(label, details=None):
    stats["ko"] += 1
    ko_in_exercise[0] += 1
    print(f"  {KO} {label}")
    if ko_in_exercise[0] == MAX_DETAILED_KO + 1:
        print(f"       {DIM}(details hidden for the rest: fix the first "
              f"KOs first){RESET}")
    if details and ko_in_exercise[0] <= MAX_DETAILED_KO:
        for line in details:
            print(f"       {line}")


def report_skip(label):
    print(f"  {SKIP} {label}")


def shorten(line, limit=70):
    if len(line) <= limit:
        return line
    return f"{line[:limit]}... ({len(line)} characters)"


def cat_e(text):
    """Like `cat -e`: a $ marks the end of each line."""
    if text == "":
        return ["(nothing)"]
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
        return [shorten(line) + "$" for line in lines]
    return ([shorten(line) + "$" for line in lines[:-1]]
            + [shorten(lines[-1]) + "  (no \\n)"])


def diff_details(expected, got, inputs=None, args=None):
    details = []
    if args:
        shown = ", ".join(repr(a) for a in args)
        details.append(f"{DIM}call: ft_seed_inventory({shown}){RESET}")
    elif inputs is not None:
        shown = ", ".join(shorten(repr(i), 40) for i in inputs) \
            if inputs else "(none)"
        details.append(f"{DIM}typed input: {shown}{RESET}")
    exp_lines = cat_e(expected)
    got_lines = cat_e(got)
    if len(exp_lines) <= 12 and len(got_lines) <= 12:
        details.append(f"{GREEN}expected:{RESET}")
        details += [f"  {line}" for line in exp_lines]
        details.append(f"{RED}got:{RESET}")
        details += [f"  {line}" for line in got_lines]
        return details
    for i in range(max(len(exp_lines), len(got_lines))):
        e = exp_lines[i] if i < len(exp_lines) else "(fin)"
        g = got_lines[i] if i < len(got_lines) else "(fin)"
        if e != g:
            details.append(f"first difference at line {i + 1}:")
            details.append(f"{GREEN}expected:{RESET} {e}")
            details.append(f"{RED}got:     {RESET} {g}")
            break
    return details


# --------------------------------------------------------------------------- #
#  Running a function with simulated keyboard input                          #
# --------------------------------------------------------------------------- #

class TooManyInputs(Exception):
    pass


class Timeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise Timeout()


def run(func, inputs=(), args=()):
    """Run func while simulating the keyboard.

    Returns (transcript, error, unread_inputs). The transcript looks like
    what you would see in a terminal: the input() prompt, followed by what
    was typed, then a newline.
    """
    feed = list(inputs)
    out = io.StringIO()

    def fake_input(prompt=""):
        if not feed:
            raise TooManyInputs()
        value = feed.pop(0)
        out.write(str(prompt) + value + "\n")
        return value

    old_input = builtins.input
    builtins.input = fake_input
    old_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(3)
    error = None
    try:
        with redirect_stdout(out):
            func(*args)
    except TooManyInputs:
        error = "input() is called more times than expected"
    except Timeout:
        error = "3s timeout exceeded (infinite loop?)"
    except RecursionError:
        error = "RecursionError (recursion never stops?)"
    except Exception as exc:  # noqa: BLE001
        error = f"crash : {type(exc).__name__}: {exc}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        builtins.input = old_input
    return out.getvalue(), error, feed


def check_case(func, label, inputs, expected, args=()):
    got, error, leftover = run(func, inputs, args)
    if error:
        report_ko(label, [error] + diff_details(expected, got, inputs, args))
        return got
    if leftover:
        report_ko(label, ["input() is not called enough times"]
                  + diff_details(expected, got, inputs, args))
        return got
    if got != expected:
        report_ko(label, diff_details(expected, got, inputs, args))
        return got
    report_ok(label)
    return got


# --------------------------------------------------------------------------- #
#  Static checks (structure, authorized functions, flake8, mypy)             #
# --------------------------------------------------------------------------- #

def find_file(ex_num, filename):
    for folder in (f"ex{ex_num}", f"ex0{ex_num}"):
        path = ROOT / folder / filename
        if path.is_file():
            return path
    return None


def check_structure(path, tree, required):
    problems = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            continue
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            continue  # docstring
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            problems.append(f"line {node.lineno}: imports are not allowed")
            continue
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test):
            problems.append(f"line {node.lineno}: "
                            "if __name__ == \"__main__\" is not allowed")
            continue
        problems.append(f"line {node.lineno}: code outside a function"
                        f" -> {ast.unparse(node).splitlines()[0]}")
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in required:
        if name not in defined:
            problems.append(f"function '{name}' not found"
                            " (check the spelling)")
    if problems:
        report_ko("file structure", problems)
        return False
    report_ok("structure (only the requested function)")
    return True


def check_authorized(tree, allowed, allow_methods=False, allow_helpers=False):
    defined = {n.name for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef)}
    params = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            params |= {a.arg for a in fn.args.args}
    problems = []
    calls = [node for fn in tree.body if isinstance(fn, ast.FunctionDef)
             for node in ast.walk(fn) if isinstance(node, ast.Call)]
    for node in calls:
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in allowed:
                continue
            if name in defined:
                if allow_helpers or name in params:
                    continue
                # call to one of your own functions: only allowed in ex6
                problems.append(f"line {node.lineno}: call to '{name}'"
                                " (helper functions not allowed here)")
                continue
            problems.append(f"line {node.lineno}: '{name}()' is not allowed")
        elif isinstance(node.func, ast.Attribute):
            if allow_methods:
                continue
            problems.append(f"line {node.lineno}: method "
                            f"'.{node.func.attr}()' is not allowed")
        else:
            problems.append(f"line {node.lineno}: call not allowed")
    if problems:
        report_ko("authorized functions: " + ", ".join(sorted(allowed)),
                  sorted(set(problems)))
        return
    report_ok("authorized functions: " + ", ".join(sorted(allowed)))


def run_tool(module, path, label):
    try:
        proc = subprocess.run([sys.executable, "-m", module, str(path)],
                              capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        report_skip(f"{label}: too slow, skipped")
        return
    output = (proc.stdout + proc.stderr).strip()
    if "No module named" in output:
        report_skip(f"{label} not installed "
                    f"(python3 -m pip install --user {module})")
        return
    if proc.returncode == 0:
        report_ok(label)
        return
    report_ko(label, output.splitlines()[:15])


def load(path, ex_num):
    """Import the student file. Nothing should run at import time."""
    spec = importlib.util.spec_from_file_location(
        f"student_ex{ex_num}_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    out = io.StringIO()

    def no_input(prompt=""):
        raise TooManyInputs()

    old_input = builtins.input
    builtins.input = no_input
    try:
        with redirect_stdout(out):
            spec.loader.exec_module(module)
    except TooManyInputs:
        report_ko("file import",
                  ["input() is called at import time: is your function "
                   "called directly in the file?"])
        return None
    except SyntaxError as exc:
        report_ko("file import",
                  [f"SyntaxError line {exc.lineno}: {exc.msg}"])
        return None
    except Exception as exc:  # noqa: BLE001
        report_ko("file import", [f"{type(exc).__name__}: {exc}"])
        return None
    finally:
        builtins.input = old_input
    if out.getvalue():
        report_ko("file import",
                  ["something is printed at import time: is your function "
                   "called directly in the file?"])
        return None
    return module


def prepare(ex_num, filename, required, allowed, **kwargs):
    """Common checks. Returns the imported module, or None."""
    path = find_file(ex_num, filename)
    if path is None:
        report_ko(f"file ex{ex_num}/{filename} not found",
                  ["check the folder and file names "
                   "(extra space? typo?)"])
        return None, None
    source = path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        report_ko("syntax", [f"line {exc.lineno}: {exc.msg}"])
        return None, None
    structure_ok = check_structure(path, tree, required)
    check_authorized(tree, allowed, **kwargs)
    run_tool("flake8", path, "flake8")
    if not structure_ok:
        return None, tree
    module = load(path, ex_num)
    return module, tree


def header(ex_num, title):
    ko_in_exercise[0] = 0
    print(f"\n{BOLD}=== ex{ex_num} : {title} ==={RESET}")


# --------------------------------------------------------------------------- #
#  Exercises                                                                  #
# --------------------------------------------------------------------------- #

def test_ex0():
    header(0, "ft_hello_garden")
    mod, _ = prepare(0, "ft_hello_garden.py", ["ft_hello_garden"], {"print"})
    if mod is None:
        return
    check_case(mod.ft_hello_garden, "prints the welcome message", [],
               "Hello, Garden Community!\n")
    check_case(mod.ft_hello_garden, "second call: same output", [],
               "Hello, Garden Community!\n")


def test_ex1():
    header(1, "ft_garden_name")
    mod, _ = prepare(1, "ft_garden_name.py", ["ft_garden_name"],
                     {"input", "print"})
    if mod is None:
        return
    cases = [
        ("subject example", "Community Garden"),
        ("one-word name", "Jardin"),
        ("empty name (just Enter)", ""),
        ("leading/trailing spaces kept", "   Rose Garden   "),
        ("accents and emoji", "Jardin d'Été 🌱"),
        ("digits", "42"),
        ("very long name", "A" * 500),
        ("special characters", "{name} %s \\n $HOME"),
    ]
    for label, name in cases:
        expected = (f"Enter garden name: {name}\n"
                    f"Garden: {name}\n"
                    "Status: Growing well!\n")
        check_case(mod.ft_garden_name, label, [name], expected)


def _two_numbers(prompts, result_label, op, mod_func, cases):
    for label, values in cases:
        expected = "".join(f"{p}{v}\n" for p, v in zip(prompts, values))
        expected += f"{result_label}{op(*[int(v) for v in values])}\n"
        check_case(mod_func, label, list(values), expected)


def test_ex2():
    header(2, "ft_plot_area")
    allowed = {"input", "int", "print"}
    mod, _ = prepare(2, "ft_plot_area.py", ["ft_plot_area"], allowed)
    if mod is None:
        return
    cases = [
        ("subject example (5 x 3)", ("5", "3")),
        ("square (4 x 4)", ("4", "4")),
        ("1 x 1", ("1", "1")),
        ("length 0", ("0", "7")),
        ("width 0", ("7", "0")),
        ("0 x 0", ("0", "0")),
        ("very large numbers", ("123456789", "987654321")),
        ("spaces around the number", (" 6 ", "  2")),
        ("leading zeros (007)", ("007", "3")),
    ]
    _two_numbers(["Enter length: ", "Enter width: "], "Plot area: ",
                 lambda a, b: a * b, mod.ft_plot_area, cases)


def test_ex3():
    header(3, "ft_harvest_total")
    allowed = {"input", "int", "print"}
    mod, _ = prepare(3, "ft_harvest_total.py", ["ft_harvest_total"], allowed)
    if mod is None:
        return
    cases = [
        ("subject example (5 + 8 + 3)", ("5", "8", "3")),
        ("all zeros", ("0", "0", "0")),
        ("only one non-zero day", ("0", "12", "0")),
        ("numbers added, not glued as text (1+2+3)", ("1", "2", "3")),
        ("very large numbers", ("999999999999", "1", "999999999999")),
        ("spaces around", (" 4", "4 ", " 4 ")),
    ]
    _two_numbers(["Day 1 harvest: ", "Day 2 harvest: ", "Day 3 harvest: "],
                 "Total harvest: ", lambda a, b, c: a + b + c,
                 mod.ft_harvest_total, cases)


def test_ex4():
    header(4, "ft_plant_age")
    allowed = {"input", "int", "print"}
    mod, _ = prepare(4, "ft_plant_age.py", ["ft_plant_age"], allowed)
    if mod is None:
        return
    ready = "Plant is ready to harvest!\n"
    grow = "Plant needs more time to grow.\n"
    cases = [
        ("subject example: 75", "75", ready),
        ("subject example: 45", "45", grow),
        ("limit: exactly 60 (not yet)", "60", grow),
        ("limit: 61 (ready)", "61", ready),
        ("limit: 59", "59", grow),
        ("0 days", "0", grow),
        ("very old: 100000", "100000", ready),
        ("spaces around: ' 61 '", " 61 ", ready),
    ]
    for label, age, result in cases:
        check_case(mod.ft_plant_age, label, [age],
                   f"Enter plant age in days: {age}\n{result}")


def test_ex5():
    header(5, "ft_water_reminder")
    allowed = {"input", "int", "print"}
    mod, _ = prepare(5, "ft_water_reminder.py", ["ft_water_reminder"],
                     allowed)
    if mod is None:
        return
    water = "Water the plants!\n"
    fine = "Plants are fine\n"
    cases = [
        ("subject example: 4", "4", water),
        ("subject example: 1", "1", fine),
        ("limit: exactly 2 (still fine)", "2", fine),
        ("limit: 3 (needs water)", "3", water),
        ("0 days (watered today)", "0", fine),
        ("a long time: 365", "365", water),
        ("spaces around: ' 3 '", " 3 ", water),
    ]
    for label, days, result in cases:
        check_case(mod.ft_water_reminder, label, [days],
                   f"Days since last watering: {days}\n{result}")


def _count_expected(n):
    text = f"Days until harvest: {n}\n"
    text += "".join(f"Day {i}\n" for i in range(1, int(n) + 1))
    return text + "Harvest time!\n"


def _has_loop(func_node):
    return any(isinstance(n, (ast.For, ast.While, ast.ListComp,
                              ast.GeneratorExp))
               for n in ast.walk(func_node))


def _is_recursive(tree):
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == fn.name):
                return True
    return False


def test_ex6():
    header(6, "ft_count_harvest (iterative + recursive)")
    allowed = {"input", "int", "print", "range"}
    cases = [
        ("subject example: 5", "5"),
        ("a single day: 1", "1"),
        ("edge case: 0 (only 'Harvest time!')", "0"),
        ("2 days", "2"),
        ("10 days (checks Day 10)", "10"),
        ("spaces around: ' 3 '", " 3 "),
        ("many days: 300", "300"),
    ]
    outputs = {}
    for kind in ("iterative", "recursive"):
        name = f"ft_count_harvest_{kind}"
        print(f"  {DIM}--- {name}.py ---{RESET}")
        mod, tree = prepare(6, f"{name}.py", [name], allowed,
                            allow_helpers=True)
        if tree is not None:
            if kind == "iterative":
                if _has_loop(tree):
                    report_ok("actually uses a loop")
                else:
                    report_ko("actually uses a loop",
                              ["no for/while loop found"])
            else:
                problems = []
                if not _is_recursive(tree):
                    problems.append("no function calls itself")
                if _has_loop(tree):
                    problems.append("there is a loop: the recursive "
                                    "version should not have one")
                if problems:
                    report_ko("actually recursive", problems)
                else:
                    report_ok("actually recursive (and loop-free)")
        if mod is None:
            continue
        func = getattr(mod, name)
        outputs[kind] = [check_case(func, label, [n], _count_expected(n))
                         for label, n in cases]
    if len(outputs) == 2:
        if outputs["iterative"] == outputs["recursive"]:
            report_ok("iterative and recursive print exactly the same")
        else:
            report_ko("iterative and recursive print exactly the same",
                      ["the two versions print different output"])


def _check_signature(tree):
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name == "ft_seed_inventory"), None)
    if fn is None:
        return
    want = [("seed_type", "str"), ("quantity", "int"), ("unit", "str")]
    got = [(a.arg, ast.unparse(a.annotation) if a.annotation else None)
           for a in fn.args.args]
    ret = ast.unparse(fn.returns) if fn.returns else None
    problems = []
    if got != want:
        problems.append("expected parameters: seed_type: str, "
                        "quantity: int, unit: str")
        problems.append("found parameters:    " + ", ".join(
            f"{a}: {t}" if t else f"{a} (no type)" for a, t in got))
    if ret != "None":
        problems.append("expected return: -> None (found: "
                        f"{ret if ret else 'nothing'})")
    label = ("signature: def ft_seed_inventory(seed_type: str, "
             "quantity: int, unit: str) -> None")
    if problems:
        report_ko(label, problems)
    else:
        report_ok(label)


def test_ex7():
    header(7, "ft_seed_inventory")
    mod, tree = prepare(7, "ft_seed_inventory.py", ["ft_seed_inventory"],
                        {"print"}, allow_methods=True)
    if tree is not None:
        _check_signature(tree)
    path = find_file(7, "ft_seed_inventory.py")
    if path is not None:
        run_tool("mypy", path, "mypy (typing)")
    if mod is None:
        return
    unknown = "Unknown unit type\n"
    cases = [
        ("subject: tomato 15 packets", ("tomato", 15, "packets"),
         "Tomato seeds: 15 packets available\n"),
        ("subject: carrot 8 grams", ("carrot", 8, "grams"),
         "Carrot seeds: 8 grams total\n"),
        ("subject: lettuce 12 area", ("lettuce", 12, "area"),
         "Lettuce seeds: covers 12 square meters\n"),
        ("unknown unit: kg", ("tomato", 3, "kg"), unknown),
        ("empty unit", ("tomato", 3, ""), unknown),
        ("capitalized unit: 'Packets' (unknown)",
         ("tomato", 3, "Packets"), unknown),
        ("singular unit: 'packet' (unknown)",
         ("tomato", 3, "packet"), unknown),
        ("quantity 0", ("basil", 0, "packets"),
         "Basil seeds: 0 packets available\n"),
        ("large quantity", ("pea", 1000000, "grams"),
         "Pea seeds: 1000000 grams total\n"),
        ("seed already capitalized", ("Radish", 4, "area"),
         "Radish seeds: covers 4 square meters\n"),
        ("seed in ALL CAPS", ("ONION", 2, "packets"),
         "Onion seeds: 2 packets available\n"),
        ("one-letter seed", ("x", 1, "grams"),
         "X seeds: 1 grams total\n"),
    ]
    for label, args, expected in cases:
        check_case(mod.ft_seed_inventory, label, [], expected, args=args)


# --------------------------------------------------------------------------- #

TESTS = [test_ex0, test_ex1, test_ex2, test_ex3,
         test_ex4, test_ex5, test_ex6, test_ex7]


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "all":
        selected = TESTS
    elif target.startswith("ex") and target[2:].isdigit() \
            and int(target[2:]) < len(TESTS):
        selected = [TESTS[int(target[2:])]]
    else:
        print(f"Unknown target: {target} (use all, ex0 ... ex7)")
        sys.exit(1)
    print(f"{DIM}Testing project: {ROOT}{RESET}")
    for test in selected:
        test()
    total = stats["ok"] + stats["ko"]
    color = GREEN if stats["ko"] == 0 else RED
    print(f"\n{BOLD}{color}Result: {stats['ok']}/{total} OK"
          f" - {stats['ko']} KO{RESET}\n")


if __name__ == "__main__":
    main()
