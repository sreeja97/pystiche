from abc import abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, cast

import torch
from torch import hub, nn
from torch.nn.modules.module import _IncompatibleKeys

from ..multi_layer_encoder import MultiLayerEncoder
from ..preprocessing import get_preprocessor

__all__ = ["ModelMultiLayerEncoder", "select_url"]

T = TypeVar("T")


def select_url(
    urls: Dict[T, str], key: T, format: Optional[Callable[[T], str]] = None
) -> str:
    if format is None:
        format = str

    try:
        return urls[key]
    except KeyError as error:
        raise RuntimeError(f"No URL is available for\n\n{format(key)}") from error


class ModelMultiLayerEncoder(MultiLayerEncoder):
    r"""Multi-layer encoder based on a pre-defined model.

    Args:
        pretrained: If ``True``, loads builtin weights. Defaults to ``True``.
        framework: Name of the framework that was used to train the builtin weights.
            Defaults to ``"torch"``.
        internal_preprocessing: If ``True``, adds a preprocessing layer for the
            selected ``framework`` as first layer. Defaults to ``True``.
        allow_inplace: If ``True``, allows inplace operations to reduce the memory
            requirement during the forward pass. Defaults to ``False``.

            .. warning::
                After performing an inplace operation the encodings of the previous
                layer is no longer accessible. Only use this if you are sure that you
                do **not** need these encodings.
    """

    def __init__(
        self,
        pretrained: bool = True,
        framework: str = "torch",
        internal_preprocessing: bool = True,
        allow_inplace: bool = True,
    ) -> None:
        self.pretrained = pretrained
        self.framework = framework
        self.internal_preprocessing = internal_preprocessing
        self.allow_inplace = allow_inplace

        modules, self._state_dict_key_map = self.collect_modules(allow_inplace)
        if internal_preprocessing:
            modules.insert(0, ("preprocessing", get_preprocessor(framework)))

        super().__init__(modules)

        if pretrained:
            self.load_state_dict_from_url(framework)

    @abstractmethod
    def state_dict_url(self, framework: str) -> str:
        r"""Select URL of a downloadable ``state_dict``.

        Args:
            framework: Name of the framework that was used to train the weights.

        Raises:
            RuntimeError: If no ``state_dict`` is available.
        """
        pass

    @abstractmethod
    def collect_modules(
        self, inplace: bool
    ) -> Tuple[List[Tuple[str, nn.Module]], Dict[str, str]]:
        r"""Collect modules of a base model with more descriptive names.

        Args:
            inplace: If ``True``, when possible, modules should use inplace operations.

        Returns:
            List of name-module-pairs as well as a dictionary mapping the new, more
            descriptive names to the original ones.
        """
        pass

    def _map_state_dict_keys(
        self, state_dict: Dict[str, torch.Tensor]
    ) -> Tuple[Dict[str, torch.Tensor], List[str]]:
        remapped_state_dict = {}
        unexpected_keys = []
        for key, value in state_dict.items():
            if key in self._state_dict_key_map:
                remapped_state_dict[self._state_dict_key_map[key]] = value
            else:
                unexpected_keys.append(key)

        return remapped_state_dict, unexpected_keys

    def load_state_dict(
        self,
        state_dict: Dict[str, torch.Tensor],
        strict: bool = True,
        map_names: bool = True,
        framework: str = "unknown",
    ) -> _IncompatibleKeys:
        r"""Loads parameters and buffers from the ``state_dict``.

        Args:
            state_dict: State dictionary.
            strict: Enforce matching keys in ``state_dict`` and the internal states.
            map_names: If ``True``, maps the names names in ``state_dict`` of the
                underlying model to the more descriptive names generated by
                :meth:`collect_modules`. Defaults to ``True``.
            framework: Name of the framework that was used to train the weights in
                ``state_dict``. Defaults to ``"unknown"``.

                .. note::

                    This has no effect on the behavior, but makes the representation
                    of the :class:`ModelMultiLayerEncoder` more descriptive.

        Returns:
            Named tuple with ``missing_keys`` and ``unexpected_keys`` fields.

        .. seealso::

            :meth:`torch.nn.Module.load_state_dict`
        """
        if map_names:
            state_dict, unexpected_keys = self._map_state_dict_keys(state_dict)
        else:
            unexpected_keys = []

        keys = cast(
            _IncompatibleKeys, super().load_state_dict(state_dict, strict=strict)
        )
        keys.unexpected_keys.extend(unexpected_keys)

        self.pretrained = True
        self.framework = framework

        return keys

    def load_state_dict_from_url(
        self,
        framework: str,
        strict: bool = True,
        map_names: bool = True,
        check_hash: bool = True,
        **kwargs: Any,
    ) -> None:
        r"""Downloads and loads parameters and buffers trained with ``framework``.

        Args:
            framework: Name of the framework that was used to train the weights of the
                ``state_dict``.
            strict: Enforce matching keys in ``state_dict`` and the internal states.
            map_names: If ``True``, maps the names names in ``state_dict`` of the
                underlying model to the more descriptive names generated by
                :meth:`collect_modules`. Defaults to ``True``.
            check_hash: If ``True``, checks if the hash postfix of the URL matches the
                SHA256 hash of the downloaded ``state_dict``. Defaults to ``True``.
            kwargs: Optional arguments for :meth:`torch.hub.load_state_dict_from_url` .

        .. seealso::

            - :meth:`state_dict_url`
            - :meth:`load_state_dict`
            - :meth:`torch.hub.load_state_dict_from_url`
        """
        url = self.state_dict_url(framework)
        state_dict = hub.load_state_dict_from_url(url, check_hash=check_hash, **kwargs)
        self.load_state_dict(
            state_dict, strict=strict, map_names=map_names, framework=framework
        )

    def _properties(self) -> Dict[str, Any]:
        dct = super()._properties()
        if not self.pretrained:
            dct["pretrained"] = False
        else:
            dct["framework"] = self.framework
        if not self.internal_preprocessing:
            dct["internal_preprocessing"] = self.internal_preprocessing
        if self.allow_inplace:
            dct["allow_inplace"] = self.allow_inplace
        return dct
