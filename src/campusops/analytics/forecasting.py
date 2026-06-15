from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


CENT = Decimal("0.01")


def number(value: object) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ForecastPoint:
    period: str
    actual: Decimal | str | int | float

    def __post_init__(self) -> None:
        if not str(self.period).strip():
            raise ValueError("forecast period is required")
        object.__setattr__(self, "period", str(self.period).strip())
        object.__setattr__(self, "actual", number(self.actual))


@dataclass(frozen=True)
class ForecastResult:
    method: str
    periods: tuple[str, ...]
    values: tuple[Decimal, ...]

    def to_rows(self) -> list[dict[str, str]]:
        return [
            {"period": period, "forecast": str(value.quantize(CENT)), "method": self.method}
            for period, value in zip(self.periods, self.values)
        ]


class MovingAverageForecaster:
    def __init__(self, window: int = 3) -> None:
        window = int(window)
        if window <= 0:
            raise ValueError("forecast window must be positive")
        self.window = window

    def forecast(self, points: Iterable[ForecastPoint], future_periods: Iterable[object]) -> ForecastResult:
        history = [point.actual for point in points]
        if not history:
            raise ValueError("forecast history is required")

        outputs: list[Decimal] = []
        periods = tuple(str(period).strip() for period in future_periods)

        for _period in periods:
            window_values = history[-self.window :]
            value = (sum(window_values, Decimal("0.00")) / Decimal(len(window_values))).quantize(CENT)
            outputs.append(value)
            history.append(value)

        return ForecastResult("moving_average", periods, tuple(outputs))


class WeightedTrendForecaster:
    def __init__(self, trend_weight: Decimal | str | int | float = "0.50") -> None:
        weight = Decimal(str(trend_weight))
        if weight < 0 or weight > 1:
            raise ValueError("trend weight must be between 0 and 1")
        self.trend_weight = weight

    def forecast(self, points: Iterable[ForecastPoint], future_periods: Iterable[object]) -> ForecastResult:
        history = [point.actual for point in points]
        if len(history) < 2:
            raise ValueError("at least two history points are required")

        last = history[-1]
        previous = history[-2]
        trend = last - previous
        outputs: list[Decimal] = []
        periods = tuple(str(period).strip() for period in future_periods)

        for _period in periods:
            next_value = (last + (trend * self.trend_weight)).quantize(CENT)
            outputs.append(next_value)
            trend = next_value - last
            last = next_value

        return ForecastResult("weighted_trend", periods, tuple(outputs))
