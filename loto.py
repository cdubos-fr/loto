import csv
import pathlib
import random
import re
import warnings
from collections.abc import Generator
from collections.abc import Iterable
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from typing import NamedTuple
from typing import TypedDict

import click


class FileFormat(TypedDict):
    cls: type[Any]
    kwargs: dict[str, Any]
    header: str


SUPPORTED_FORMATS: dict[str, FileFormat] = {
    ".csv": FileFormat(cls=csv.DictReader, kwargs={"delimiter": ";"}, header="fieldnames"),
}


class LotoResult(NamedTuple):
    grid: Sequence[int]
    chance: Sequence[int]
    date: datetime | None = None

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        if self.date is not None:
            date = f" le {self.date:%d-%m-%Y}"
        else:
            date = ""
        return (
            f"tirage={'-'.join(map(str, sorted(self.grid)))}+"
            f"{'+'.join(map(str, sorted(self.chance)))}{date}"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LotoResult):
            raise NotImplementedError
        if len(self.grid) == len(other.grid):
            return sorted(self.grid) == sorted(other.grid)
        if len(self.grid) < len(other.grid):
            return all(i in other.grid for i in self.grid)
        return all(i in self.grid for i in other.grid)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, LotoResult):
            raise NotImplementedError
        return not (self == other)

    @classmethod
    def from_string(cls, input_string: str) -> "LotoResult":
        try:
            grid_str, _, chance_str = input_string.partition("+")
            grid, chance = (
                [int(i) for i in grid_str.split("-")],
                [int(i) for i in chance_str.split("+")],
            )
        except Exception:
            raise ValueError(f"Invalie format for {input_string}")

        return cls(grid, chance)


def formatter(prefix: str, idx: int) -> str:
    return f'{prefix}{idx}'


class LotoFormat(Iterable[LotoResult]):
    CHANCE_NB: int
    CHANCE_PREFIX: str
    BOULES_NB: int
    BOULE_PREFIX: str = "boule_"
    DATE_KEY = "date_de_tirage"
    MAX = 49
    MAX_CHANCE = 10
    WHITELIST_BOULE: str | None = None

    def __init__(self, reader: Any):
        self.reader = reader

    def __iter__(self) -> Generator[LotoResult, None, None]:
        for line in self.reader:
            yield from self.extract_line(line)

    @classmethod
    def boule_keys(cls) -> list[str]:
        if cls.BOULES_NB == 1:
            return [cls.BOULE_PREFIX]
        return [*(formatter(cls.BOULE_PREFIX, i) for i in range(1, cls.BOULES_NB + 1))]

    @classmethod
    def chance_keys(cls) -> list[str]:
        if cls.CHANCE_NB == 1:
            return [cls.CHANCE_PREFIX]
        return [*(formatter(cls.CHANCE_PREFIX, i) for i in range(1, cls.CHANCE_NB + 1))]

    @classmethod
    def whitelist(cls, key: str) -> bool:
        if cls.WHITELIST_BOULE is None:
            return False
        return re.match(cls.WHITELIST_BOULE, key) is not None

    @classmethod
    def is_one(cls, to_compare: LotoResult | Sequence[str]) -> bool:
        if isinstance(to_compare, LotoResult):
            return (
                len(set(to_compare.grid)) == cls.BOULES_NB and
                len(set(to_compare.chance)) == cls.CHANCE_NB and
                all(0 < i <= cls.MAX for i in to_compare.grid) and
                all(0 < i <= cls.MAX_CHANCE for i in to_compare.chance)
            )
        return (
            all(boule in to_compare for boule in cls.boule_keys()) and
            all(chance in to_compare for chance in cls.chance_keys()) and
            len([
                h for h in to_compare
                if (
                    h.startswith(cls.BOULE_PREFIX) or
                    h.startswith(cls.CHANCE_PREFIX)
                ) and (
                    h not in (
                        cls.boule_keys()
                        + cls.chance_keys()
                    )
                ) and not cls.whitelist(h)
            ]) == 0
        )

    def extract_line(self, line: dict[str, Any]) -> list[LotoResult]:
        grid = tuple(int(line[boule]) for boule in self.boule_keys())
        chance = tuple(int(line[boule]) for boule in self.chance_keys())
        loto_date = line[self.DATE_KEY]
        for date_fmt in find_date_format(loto_date):
            try:
                return [LotoResult(grid, chance, datetime.strptime(loto_date, date_fmt))]
            except Exception as e:
                warnings.warn(str(e))
        return []

    @classmethod
    def generate(cls) -> LotoResult:
        return LotoResult(
            random.sample(
                range(
                    1,
                    cls.MAX + 1,
                ),
                k=cls.BOULES_NB,
            ),
            random.sample(
                range(
                    1,
                    cls.MAX_CHANCE + 1,
                ),
                k=cls.CHANCE_NB,
            ),
        )


class Loto5Boules(LotoFormat):
    """Loto format since 2008"""
    CHANCE_PREFIX: str = "numero_chance"
    CHANCE_NB: int = 1
    BOULES_NB: int = 5
    WHITELIST_BOULE: str = r"boule_[1-5]_second_tirage"

    def extract_line(self, line: dict[str, Any]) -> list[LotoResult]:
        res = super().extract_line(line)
        second_format = "boule_{}_second_tirage"
        seq = []
        for i in range(1, self.BOULES_NB + 1):
            if (f := second_format.format(i)) in line:
                seq.append(int(line[f]))
        if seq:
            res.append(LotoResult(seq, tuple(int(line[boule]) for boule in self.chance_keys())))
        return res


class Loto6Boules(LotoFormat):
    """Loto format before 2008"""
    CHANCE_PREFIX: str = "boule_complementaire"
    CHANCE_NB: int = 1
    BOULES_NB: int = 6


class EuroMillion(LotoFormat):
    """EuroMillion"""
    CHANCE_PREFIX: str = "etoile_"
    MAX_CHANCE: int = 12
    CHANCE_NB: int = 2
    BOULES_NB: int = 5
    MAX = 50


LOTO_FORMATS: dict[str, type[LotoFormat]] = {
    "5_boules": Loto5Boules,
    "6_boules": Loto6Boules,
    "euromillion": EuroMillion,
}


def find_date_format(getted_date: str) -> Generator[str, None, None]:
    if "/" in getted_date:
        yield "%d/%m/%Y"
        yield "%d/%m/%y"
    yield "%Y%m%d"


def read_loto_file(filename: pathlib.Path) -> Iterable[LotoResult]:
    with open(filename) as f:
        format_reader = SUPPORTED_FORMATS[filename.suffix]
        try:
            reader = format_reader["cls"](f, **format_reader["kwargs"])
            header = getattr(reader, format_reader["header"])
            for data_cls in LOTO_FORMATS.values():
                if data_cls.is_one(header):
                    return [i for i in data_cls(reader)]
            warnings.warn(f"No format found to process {filename} with header={header}")
            return []
        except Exception as e:
            print(f"An error occur when processing {filename} with {format_reader}: {e}")
            return []


def generate_tirage(results: list[LotoResult], loto_cls: type[LotoFormat]) -> LotoResult:
    print(f"Generation for {loto_cls}")
    while (gen := loto_cls.generate()) in results:
        continue
    return gen


@click.command()
@click.option(
    "-r", "--repository", type=click.Path(
        exists=True,
        file_okay=False, path_type=pathlib.Path,
    ),
)
@click.option(
    "-f", "--file", type=click.Path(
        exists=True, dir_okay=False,
        path_type=pathlib.Path,
    ), default=[], multiple=True,
)
@click.option(
    "-l",
    "--loto-format",
    type=click.Choice(list(LOTO_FORMATS.keys())),
    default="5_boules",
)
@click.option("-e", "--exist", type=str, default=None)
@click.pass_context
def main(
    ctx: click.Context, repository: pathlib.Path,
    file: list[pathlib.Path], loto_format: str, exist: str | None,
) -> None:
    if repository and file:
        raise click.exceptions.UsageError(
            "--repository and --file can't be set simultaneously", ctx=ctx,
        )
    if not (repository or file):
        raise click.exceptions.UsageError("one of --repository or --file should be set", ctx=ctx)
    if any(f.suffix not in SUPPORTED_FORMATS for f in file):
        raise click.exceptions.BadParameter(
            f"--file must be one of {', '.join(SUPPORTED_FORMATS)}", ctx=ctx,
        )

    if repository:
        files = [f for f in repository.iterdir() if f.suffix in SUPPORTED_FORMATS]
        if not files:
            warnings.warn(f"no file found for accepted format: {', '.join(SUPPORTED_FORMATS)}")
    else:
        files = file
    results = [line for f in files for line in read_loto_file(f)]
    loto_cls = LOTO_FORMATS[loto_format]
    if exist is not None:
        try:
            exist_result = LotoResult.from_string(exist)
        except Exception as e:
            raise click.exceptions.BadArgumentUsage(str(e))
        click.echo(f"Is a valid {loto_cls.__name__} ? {loto_cls.is_one(exist_result)}")
        click.echo(f"{exist_result} was drawn ? {exist_result in results}")
    else:
        click.echo(generate_tirage(results, loto_cls))
