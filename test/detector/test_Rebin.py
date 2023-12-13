from matplotlib import pyplot as plt
from numpy import allclose, finfo, linspace, matmul
from numpy.typing import NDArray
from pytest import mark, raises

from dagflow.graph import Graph
from dagflow.graphviz import savegraph
from dagflow.lib import Array
from dagflow.plot import closefig, plot_array_1d_hist, savefig

from detector.Rebin import Rebin
from detector.RebinMatrix import RebinMatrix


def partial_sum(y_old: NDArray, m: int) -> list:
    psum = []
    i = 0
    while i < y_old.size:
        psum.append(y_old[i : i + m].sum())
        i += m
    return psum


@mark.parametrize("dtype", ("d", "f"))
@mark.parametrize("m", (2, 4))
@mark.parametrize("mode", ("python", "numba"))
def test_Rebin(testname, m, dtype, mode):
    n = 21
    edges_old = linspace(0.0, 2.0, n, dtype=dtype)
    edges_new = edges_old[::m]
    y_old_list = [linspace(3.0, 0.0, n - 1, dtype=dtype), linspace(2.0, 0.0, n - 1, dtype=dtype)]

    with Graph(close=True) as graph:
        EdgesOld = Array("edges_old", edges_old)
        EdgesNew = Array("edges_new", edges_new)
        Y = Array("Y", y_old_list[0])
        Y2 = Array("Y2", y_old_list[1])
        metanode = Rebin(mode=mode)

        EdgesOld >> metanode.inputs["edges_old"]
        EdgesNew >> metanode.inputs["edges_new"]
        Y >> metanode()
        Y2 >> metanode()
        metanode.print()

    mat = metanode.outputs["matrix"].data
    # NOTE: Asserts below are only for current edges_new! For other binning it may not coincide!
    assert (mat.sum(axis=0) == 1).all()
    assert mat.sum(axis=0).sum() == n - 1

    rtol = finfo(dtype).resolution
    for i, y_old in enumerate(y_old_list):
        y_new = metanode.outputs[i].data
        y_res = matmul(mat, y_old)
        assert allclose(y_res, y_new, atol=0.0, rtol=rtol)
        assert allclose(partial_sum(y_old, m), y_new, atol=0.0, rtol=rtol)

    # plots
    plot_array_1d_hist(
        array=y_old_list[0], edges=edges_old, color="blue", label="old edges 1", linewidth=2
    )
    plot_array_1d_hist(
        array=y_old_list[1], edges=edges_old, color="orange", label="old edges 2", linewidth=2
    )
    plot_array_1d_hist(
        array=metanode.outputs[0].data,
        edges=edges_new,
        color="blue",
        linestyle="-.",
        label="new edges 1",
        linewidth=2,
    )
    plot_array_1d_hist(
        array=metanode.outputs[1].data,
        edges=edges_new,
        color="orange",
        linestyle="-.",
        label="new edges 2",
        linewidth=2,
    )
    plt.xlabel("x")
    plt.ylabel("y")
    plt.legend(fontsize="x-large")
    savefig(f"output/{testname}-plot.png")
    closefig()

    savegraph(graph, f"output/{testname}-graph.png")


@mark.parametrize(
    "edges_new",
    (
        linspace(-1.0, 2.0, 21),
        linspace(0.0, 2.1, 21),
        linspace(0.0, 2.0, 41),
        linspace(0.0, 2.0, 10),
    ),
)
@mark.parametrize("mode", ("python", "numba"))
def test_RebinMatrix_wrong_edges_new(edges_new, mode):
    edges_old = linspace(0.0, 2.0, 21)
    with Graph(close=True):
        EdgesOld = Array("edges_old", edges_old)
        EdgesNew = Array("edges_new", edges_new)
        mat = RebinMatrix("Rebin Matrix", mode=mode)
        EdgesOld >> mat("edges_old")
        EdgesNew >> mat("edges_new")
    with raises(Exception):
        mat.get_data()
