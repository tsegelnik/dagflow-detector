from __future__ import annotations

from typing import TYPE_CHECKING

from dagflow.exception import ConnectionError
from dagflow.lib import VectorMatrixProduct
from dagflow.metanode import MetaNode
from dagflow.storage import NodeStorage
from dgf_detector.RebinMatrix import RebinMatrix

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dagflow.node import Node
    from dgf_detector.RebinMatrix import RebinModesType
    from multikeydict.typing import KeyLike


class Rebin(MetaNode):
    __slots__ = ("_RebinMatrixList", "_VectorMatrixProductList")

    _RebinMatrixList: list[Node]
    _VectorMatrixProductList: list[Node]

    def __init__(
        self, *, bare: bool = False, mode: RebinModesType = "numba", labels: Mapping = {}, **kwargs
    ):
        super().__init__()
        self._RebinMatrixList = []
        self._VectorMatrixProductList = []
        if bare:
            return

        self.add_RebinMatrix(
            name="RebinMatrix", mode=mode, label=labels.get("RebinMatrix", {}), **kwargs
        )
        self.add_VectorMatrixProduct("VectorMatrixProduct", labels.get("VectorMatrixProduct", {}))
        self._bind_outputs()

    def add_RebinMatrix(
        self, name: str = "RebinMatrix", mode: RebinModesType = "numba", **kwargs
    ) -> RebinMatrix:
        _RebinMatrix = RebinMatrix(name=name, mode=mode, **kwargs)
        self._RebinMatrixList.append(_RebinMatrix)
        self._add_node(
            _RebinMatrix,
            kw_inputs=["edges_old", "edges_new"],
            kw_outputs=["matrix"],
            missing_inputs=True,
            also_missing_outputs=True,
        )
        return _RebinMatrix

    def add_VectorMatrixProduct(
        self, name: str = "VectorMatrixProduct", label: Mapping = {}
    ) -> VectorMatrixProduct:
        _VectorMatrixProduct = VectorMatrixProduct(name, mode="column", label=label)
        self._VectorMatrixProductList.append(_VectorMatrixProduct)
        self._add_node(
            _VectorMatrixProduct,
            inputs_pos=True,
            outputs_pos=True,
            kw_inputs=["matrix"],
            merge_inputs=["matrix"],
            missing_inputs=True,
            also_missing_outputs=True,
        )
        self._leading_node = _VectorMatrixProduct
        return _VectorMatrixProduct

    def _bind_outputs(self) -> None:
        if (l1 := len(self._VectorMatrixProductList)) != (l2 := len(self._RebinMatrixList)):
            raise ConnectionError(
                "Cannot bind outputs! Nodes must be pairs of (VectorMatrixProduct, RebinMatrix), "
                f"but current lengths are {l1}, {l2}!",
                node=self,
            )
        for _VectorMatrixProduct, _RebinMatrix in zip(
            self._VectorMatrixProductList, self._RebinMatrixList
        ):
            _RebinMatrix.outputs["matrix"] >> _VectorMatrixProduct.inputs["matrix"]

    @classmethod
    def replicate(
        cls,
        *,
        names: Mapping[str, str] = {
            "matrix": "rebin_matrix",
            "product": "vector_matrix_product",
        },
        path: str | None = None,
        labels: Mapping = {},
        replicate_outputs: tuple[KeyLike, ...] = ((),),
        **kwargs,
    ) -> tuple[Rebin, NodeStorage]:
        storage = NodeStorage(default_containers=True)
        nodes = storage("nodes")
        inputs = storage("inputs")
        outputs = storage("outputs")

        instance = cls(bare=True)
        key_VectorMatixProduct = tuple(names["product"].split("."))
        key_RebinMatrix = tuple(names["matrix"].split("."))
        if path:
            tpath = tuple(path.split("."))
            key_VectorMatixProduct = tpath + key_VectorMatixProduct
            key_RebinMatrix = tpath + key_RebinMatrix

        _RebinMatrix = instance.add_RebinMatrix(
            names["matrix"], label=labels.get("RebinMatrix", {}), **kwargs
        )
        nodes[key_RebinMatrix] = _RebinMatrix
        for iname, input in _RebinMatrix.inputs.iter_kw_items():
            inputs[key_RebinMatrix + (iname,)] = input
        outputs[key_RebinMatrix] = _RebinMatrix.outputs["matrix"]

        label_int = labels.get("Rebin", {})
        for key in replicate_outputs:
            if isinstance(key, str):
                key = (key,)

            name = ".".join(key_VectorMatixProduct + key)
            _VectorMatrixProduct = instance.add_VectorMatrixProduct(name, label_int)
            _VectorMatrixProduct()
            nodes[name] = _VectorMatrixProduct
            inputs[name] = _VectorMatrixProduct.inputs["vector"]
            outputs[name] = _VectorMatrixProduct.outputs["result"]
            _RebinMatrix.outputs["matrix"] >> _VectorMatrixProduct.inputs["matrix"]

        NodeStorage.update_current(storage, strict=True)
        return instance, storage
