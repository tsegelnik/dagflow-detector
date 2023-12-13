from typing import TYPE_CHECKING
from dagflow.nodes import FunctionNode

from numpy.typing import NDArray

if TYPE_CHECKING:
    from dagflow.input import Input
    from dagflow.output import Output


class AxisDistortionMatrix(FunctionNode):
    """For a given historam and distorted X axis compute the conversion matrix"""

    __slots__ = (
        "_edges_original",
        "_edges_modified",
        "_edges_backward",
        "_result",
    )

    _edges_original: "Input"
    _edges_modified: "Input"
    _edges_backward: "Input"
    _result: "Output"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.labels.setdefaults(
            {
                "text": r"Bin edges distortion matrix",
            }
        )
        self._edges_original = self._add_input("EdgesOriginal", positional=False)
        self._edges_modified = self._add_input("EdgesModified", positional=False)
        self._edges_backward = self._add_input(
            "EdgesModifiedBackwards", positional=False
        )
        self._result = self._add_output("matrix")  # output: 0

        self._functions.update(
            {
                "python": self._fcn_python,
                "numba": self._fcn_numba,
            }
        )

    def _fcn_python(self):
        _axisdistortion_python(
            self._edges_original.data,
            self._edges_modified.data,
            self._edges_backward.data,
            self._result.data,
        )

    def _fcn_numba(self):
        _axisdistortion_numba(
            self._edges_original.data,
            self._edges_modified.data,
            self._edges_backward.data,
            self._result.data,
        )

    def _typefunc(self) -> None:
        """A output takes this function to determine the dtype and shape"""
        from dagflow.typefunctions import (
            check_input_dimension,
            check_inputs_same_dtype,
            check_inputs_same_shape,
            copy_input_dtype_to_output,
            check_input_size,
            eval_output_dtype,
        )

        names_edges = ("EdgesOriginal", "EdgesModified", "EdgesModifiedBackwards")
        check_input_dimension(self, names_edges, 1)
        check_inputs_same_dtype(self, names_edges)
        (nedges,) = check_inputs_same_shape(self, names_edges)
        check_input_size(self, "EdgesOriginal", min=1)
        copy_input_dtype_to_output(self, "EdgesOriginal", "matrix")
        eval_output_dtype(self, names_edges, "matrix")

        self._result.dd.shape = (nedges - 1, nedges - 1)
        edges = self._edges_original.parent_output
        self._result.dd.axes_edges = [edges, edges]
        self.fcn = self._functions["numba"]


def _axisdistortion_python(
    edges_original: NDArray,
    edges_modified: NDArray,
    edges_backwards: NDArray,
    matrix: NDArray,
):
    # in general, target edges may be different (fine than original), the code should handle it.
    edges_target = edges_original
    min_original = edges_original[0]
    min_target = edges_target[0]
    nbinsx = edges_original.size - 1
    nbinsy = edges_target.size - 1

    matrix[:, :] = 0.0

    threshold = -1e10
    # left_axis = 0
    right_axis = 0
    idxx0, idxx1, idxy = -1, -1, 0
    leftx_fine, lefty_fine = threshold, threshold
    while (
        leftx_fine <= threshold or leftx_fine < min_original or lefty_fine < min_target
    ):
        isx = edges_original[idxx0 + 1] < edges_backwards[idxx1 + 1]
        if isx:
            leftx_fine, lefty_fine = edges_original[0], edges_modified[0]
            # left_axis = 0
            if (idxx0 := idxx0 + 1) >= nbinsx:
                return
        else:
            leftx_fine, lefty_fine = edges_backwards[0], edges_target[0]
            # left_axis = 1
            if (idxx1 := idxx1 + 1) >= nbinsx:
                return

    width_coarse = edges_original[idxx0 + 1] - edges_original[idxx0]
    while True:
        right_orig = edges_original[idxx0 + 1]
        right_backwards = edges_backwards[idxx1 + 1]

        if right_orig < right_backwards:
            rightx_fine = right_orig
            righty_fine = edges_modified[idxx0 + 1]
            right_axis = 0
        else:
            rightx_fine = right_backwards
            righty_fine = edges_target[idxx1 + 1]
            right_axis = 1

        while lefty_fine >= edges_target[idxy + 1]:
            if (idxy := idxy + 1) > nbinsy:
                break

        ##
        ## Uncomment the following lines to see the debug output
        ## (you need to also uncomment all the `left_axis` lines)
        ##
        # width_fine = rightx_fine-leftx_fine
        # factor = width_fine/width_coarse
        # print(
        #         f"x:{leftx_fine:8.4f}→{rightx_fine:8.4f}="
        #         f"{width_fine:8.4f}/{width_coarse:8.4f}={factor:8.4g} "
        #         f"ax:{left_axis}→{right_axis} idxx:{idxx0: 4d},{idxx1: 4d} iidxy: {idxy: 4d} "
        #         f"y:{lefty_fine:8.4f}→{righty_fine:8.4f}"
        # )

        matrix[idxy, idxx0] = (rightx_fine - leftx_fine) / width_coarse

        if right_axis == 0:
            if (idxx0 := idxx0 + 1) >= nbinsx:
                break
            width_coarse = edges_original[idxx0 + 1] - edges_original[idxx0]
        elif (idxx1 := idxx1 + 1) >= nbinsx:
            break
        leftx_fine, lefty_fine = rightx_fine, righty_fine
        # left_axis = right_axis


from numba import njit
from typing import Callable

_axisdistortion_numba: Callable[[NDArray, NDArray, NDArray, NDArray], None] = njit(
    cache=True
)(_axisdistortion_python)
