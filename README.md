# Growing Code tester (42 – Python Module 00)

An unofficial tester for the **Growing Code** project (*Python Fundamentals Through Garden Data*) of the 42 common core.

It checks every exercise (ex0 → ex7) against the subject's examples **and** edge cases, and prints `OK` / `KO` for each test, along with what was expected and what your code actually printed.

> ⚠️ This tester is a learning aid, not the official evaluation. Passing every test does not guarantee you'll pass your defense. Understand every line you write.

## Installation

Clone or unzip the `tester/` folder **at the root of your project**, next to your exercise folders:

```
Python_Module_00/
├── ex0/
│   └── ft_hello_garden.py
├── ex1/
│   └── ft_garden_name.py
├── ...
├── ex7/
│   └── ft_seed_inventory.py
└── tester/
    ├── Makefile
    ├── tester.py
    └── README.md
```

Both `ex0/` and `ex00/` style folder names are supported.

**Do not push `tester/` to your repository.** The subject asks you to turn in only the requested files.

### Optional: flake8 and mypy

The subject requires flake8 compliance and mypy type checking for ex7. If these tools are installed, the tester runs them too. You don't need root access:

```
python3 -m pip install --user flake8 mypy
```

If they're missing, those checks are skipped (`[--]`) instead of failing.

## Usage

```
cd tester
make all    # test every exercise
make ex3    # test a single exercise (ex0 … ex7)
```

Requires Python 3.10+ on Linux or macOS. The tester uses `signal.SIGALRM` for timeouts, so it won't run on native Windows; use WSL there.

## What it checks

For each exercise:

| Check | Description |
|---|---|
| File found | The file exists under the exact expected name (catches typos and stray spaces) |
| Structure | The file contains only function definitions: no top-level code, no `if __name__ == "__main__":`, no direct call, no imports |
| Authorized functions | Only the functions listed in the subject are called (e.g. `input`, `int`, `print`, `range`) |
| flake8 | Style compliance |
| Output | Exact output, including `input()` prompts, for the subject's examples and edge cases |

Exercise-specific checks:

- **ex1**: empty name, leading/trailing spaces, accents and emoji, very long names, special characters (`{name}`, `%s`, `$HOME`)
- **ex2 / ex3**: zeros, very large numbers, spaces around numbers, leading zeros (`007`), and that values are added as numbers, not concatenated as strings
- **ex4**: boundary values `59`, `60` (not ready, since the subject says *strictly* more than 60) and `61`
- **ex5**: boundary values `2` (fine) and `3` (water)
- **ex6**:
  - the iterative version actually uses a loop
  - the recursive version actually calls itself and has no loop
  - both versions produce identical output
  - edge cases `0`, `1`, `10` and `300` days
- **ex7**:
  - the exact signature `(seed_type: str, quantity: int, unit: str) -> None`
  - mypy
  - capitalization (`ONION` → `Onion`)
  - unknown units (`kg`, empty string, `Packets`, `packet`) print only `Unknown unit type`

## Reading the output

```
  [KO] limit: exactly 60 (not yet)
       typed input: '60'
       expected:
         Enter plant age in days: 60$
         Plant needs more time to grow.$
       got:
         Enter plant age in days: 60$
         Plant is ready to harvest!$
```

- `$` marks the end of each line (like `cat -e`), so trailing spaces become visible.
- The tester simulates keyboard input. A prompt passed to `input()` is shown followed by the typed value, just like in a real terminal.
- Only the first 3 failures of each exercise are shown in detail, so your terminal doesn't get flooded. Fix those first, then run again.
- The tester also reports crashes, infinite loops (3-second timeout), runaway recursion, and `input()` being called too many or too few times.

## How it works

The tester imports your file with `importlib` and replaces `input()` with a fake version that feeds predefined values. It captures everything printed and compares it character by character with the expected output. It reads your source code with Python's `ast` module to check the structure and the authorized functions, without running anything.

## Contributing

Found a bug, or an edge case that's missing? Open an issue or a pull request. Contributions are welcome.
