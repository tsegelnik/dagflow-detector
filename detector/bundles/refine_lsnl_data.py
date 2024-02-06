
from numpy import arange, concatenate, linspace
from numpy.typing import NDArray
from scipy.interpolate import interp1d

from multikeydict.nestedmkdict import NestedMKDict


def refine_lsnl_data(
    storage: NestedMKDict, *, edepname: str, nominalname: str, **kwargs
) -> None:
    xcoarse = storage[edepname]

    refiner = RefineGraph(xcoarse, **kwargs)

    for key, ycoarse in storage.walkitems():
        if ycoarse is xcoarse:
            continue

        nominal = storage[nominalname]
        storage[key] = refiner.process(ycoarse, nominal)

    storage[edepname] = refiner.xfine_extended


class RefineGraph:
    __slots__ = (
        "xcoarse",
        "xfine_bound",
        "xfine_extended",
        "xfine_extended_stack",
        "refine_times",
        "newmin",
        "newmax",
    )
    xcoarse: NDArray
    xfine_bound: NDArray
    xfine_extended: NDArray
    xfine_extended_stack: tuple[NDArray | None, NDArray | None, NDArray | None]
    refine_times: int
    newmin: float
    newmax: float

    def __init__(
        self,
        xcoarse: NDArray,
        *,
        refine_times: int,
        newmin: float,
        newmax: float,
    ):
        self.xcoarse = xcoarse
        self.refine_times = refine_times
        self.newmin = newmin
        self.newmax = newmax

        self._process_x()

    def make_finer_x(self) -> None:
        shape_fine = (self.xcoarse.size - 1) * self.refine_times + 1
        self.xfine_bound = linspace(self.xcoarse[0], self.xcoarse[-1], shape_fine)

    def make_extended_x(self):
        if self.newmin is None and self.newmax is None:
            return

        xstack = [None, self.xfine_bound, None]
        if self.newmin is not None:
            xstack[0] = arange(
                self.newmin,
                self.xfine_bound[0],
                self.xfine_bound[1] - self.xfine_bound[0],
            )

        if self.newmax is not None:
            stepright = self.xfine_bound[-1] - self.xfine_bound[-2]
            xstack[-1] = arange(
                self.xfine_bound[-1], self.newmax + stepright * 1.0e-6, stepright
            )[1:]

        self.xfine_extended = concatenate(xstack)
        self.xfine_extended_stack = tuple(xstack)

    def _process_x(self):
        self.make_finer_x()
        self.make_extended_x()

    def process(self, y: NDArray, nominal: NDArray) -> NDArray:
        skip_diff = y is nominal
        yabs = self._method_reltoabs(y)
        yfine = self._method_interpolate(yabs)
        yunbound = self._method_extrapolate(yfine)

        if skip_diff:
            return yunbound

        return self._method_diff(yunbound, nominal)

    def _method_reltoabs(self, yrel: NDArray) -> NDArray:
        return yrel * self.xcoarse

    def _method_interpolate(self, ycoarse) -> NDArray:
        fcn = interp1d(
            self.xcoarse,
            ycoarse,
            kind="cubic",
            bounds_error=False,
            fill_value="extrapolate",
        )
        return fcn(self.xfine_bound)

    def _method_extrapolate(self, ybound: NDArray) -> NDArray:
        fcn = interp1d(
            self.xfine_bound,
            ybound,
            kind="linear",
            bounds_error=False,
            fill_value="extrapolate",
        )

        xleft, _, xright = self.xfine_extended_stack
        ystack = [None, ybound, None]
        if xleft is not None:
            ystack[0] = fcn(xleft)
        if xright is not None:
            ystack[-1] = fcn(xright)

        return concatenate(ystack)

    def _method_diff(self, nominal: NDArray, y: NDArray) -> NDArray:
        if nominal is y:
            return nominal

        return y - nominal
