from typing import TYPE_CHECKING, Literal

from dagflow.exception import InitializationError
from dagflow.nodes import FunctionNode
from numba import njit
from numpy import isclose
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dagflow.input import Input
    from dagflow.output import Output


RebinModes = {"python", "numba"}
RebinModesType = Literal[RebinModes]


class RebinMatrix(FunctionNode):
    """For a given `edges_old` and `edges_new` computes the conversion matrix"""

    __slots__ = ("_edges_old", "_edges_new", "_result", "_atol", "_rtol", "_mode")

    _edges_old: "Input"
    _edges_new: "Input"
    _result: "Output"
    _atol: float
    _rtol: float
    _mode: str

    def __init__(
        self, *args, rtol: float = 0.0, atol: float = 1e-14, mode: RebinModesType = "numba", **kwargs
    ):
        super().__init__(*args, **kwargs, allowed_kw_inputs=("edges_old", "edges_new"))
        self.labels.setdefaults(
            {
                "text": "Matrix for rebinning",
            }
        )
        if mode not in RebinModes:
            raise InitializationError(f"mode must be in {RebinModes}, but given {mode}!", node=self)
        self._mode = mode
        self._atol = atol
        self._rtol = rtol
        self._edges_old = self._add_input("edges_old", positional=False)
        self._edges_new = self._add_input("edges_new", positional=False)
        self._result = self._add_output("matrix")  # output: 0
        self._functions.update(
            {
                "python": self._fcn_python,
                "numba": self._fcn_numba,
            }
        )

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def atol(self) -> float:
        return self._atol

    @property
    def rtol(self) -> float:
        return self._rtol

    def _fcn_python(self):
        _calc_rebin_matrix_python(
            self._edges_old.data, self._edges_new.data, self._result.data, self.atol, self.rtol
        )

    def _fcn_numba(self):
        _calc_rebin_matrix_numba(
            self._edges_old.data, self._edges_new.data, self._result.data, self.atol, self.rtol
        )

    def _typefunc(self) -> None:
        """A output takes this function to determine the dtype and shape"""
        from dagflow.typefunctions import check_input_dimension  # fmt:skip
        check_input_dimension(self, ("edges_old", "edges_new"), 1)
        self._result.dd.shape = (self._edges_new.dd.size - 1, self._edges_old.dd.size - 1)
        self._result.dd.dtype = "d"
        self.fcn = self._functions[self.mode]


def _calc_rebin_matrix_python(
    edges_old: NDArray, edges_new: NDArray, rebin_matrix: NDArray, atol: float, rtol: float
) -> None:
    """
    For a column C of size N: Cnew = M C
    Cnew = [Mx1]
    M = [MxN]
    C = [Nx1]
    """
    assert edges_new[0] >= edges_old[0] or isclose(edges_new[0], edges_old[0], atol=atol, rtol=rtol)
    assert edges_new[-1] <= edges_old[-1] or isclose(edges_new[-1], edges_old[-1], atol=atol, rtol=rtol)

    inew = 0
    iold = 0
    nold = edges_old.size
    edge_old = edges_old[0]
    edge_new_prev = edges_new[0]

    stepper_old = enumerate(edges_old)
    iold, edge_old = next(stepper_old)
    for inew, edge_new in enumerate(edges_new[1:], 1):
        while edge_old < edge_new and not isclose(edge_new, edge_old, atol=atol, rtol=rtol):
            if edge_old >= edge_new_prev or isclose(edge_old, edge_new_prev, atol=atol, rtol=rtol):
                rebin_matrix[inew - 1, iold] = 1.0

            iold, edge_old = next(stepper_old)
            if iold >= nold:
                # print("Old:", edges_old.size, edges_old)
                # print("New:", edges_new.size, edges_new)
                raise RuntimeError(f"Inconsistent edges (outer): {iold} {edge_old}, {inew} {edge_new}")

        if not isclose(edge_new, edge_old, atol=atol, rtol=rtol):
            # print("Old:", edges_old.size, edges_old)
            # print("New:", edges_new.size, edges_new)
            raise RuntimeError(f"Inconsistent edges (inner): {iold} {edge_old}, {inew} {edge_new}")


@njit(cache=True)
def _calc_rebin_matrix_numba(
    edges_old: NDArray, edges_new: NDArray, rebin_matrix: NDArray, atol: float, rtol: float
) -> None:
    """
    For a column C of size N: Cnew = M C
    Cnew = [Mx1]
    M = [MxN]
    C = [Nx1]
    """
    assert edges_new[0] >= edges_old[0] or isclose(edges_new[0], edges_old[0], atol=atol, rtol=rtol)
    assert edges_new[-1] <= edges_old[-1] or isclose(edges_new[-1], edges_old[-1], atol=atol, rtol=rtol)

    inew = 0
    iold = 0
    nold = edges_old.size
    edge_old = edges_old[0]
    edge_new_prev = edges_new[0]

    stepper_old = enumerate(edges_old)
    iold, edge_old = next(stepper_old)
    for inew, edge_new in enumerate(edges_new[1:], 1):
        while edge_old < edge_new and not isclose(edge_new, edge_old, atol=atol, rtol=rtol):
            if edge_old >= edge_new_prev or isclose(edge_old, edge_new_prev, atol=atol, rtol=rtol):
                rebin_matrix[inew - 1, iold] = 1.0

            iold, edge_old = next(stepper_old)
            assert iold < nold
            #    print("Old:", edges_old.size, edges_old)
            #    print("New:", edges_new.size, edges_new)
            #    raise RuntimeError(f"Inconsistent edges (outer): {iold} {edge_old}, {inew} {edge_new}")

        assert isclose(edge_new, edge_old, atol=atol, rtol=rtol)
        #    print("Old:", edges_old.size, edges_old)
        #    print("New:", edges_new.size, edges_new)
        #    raise RuntimeError(f"Inconsistent edges (inner): {iold} {edge_old}, {inew} {edge_new}")
