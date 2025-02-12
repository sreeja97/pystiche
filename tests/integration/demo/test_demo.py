import pytest

import torch

from pystiche import data, demo


def test_images_smoke():
    images = demo.images()
    assert isinstance(images, data.DownloadableImageCollection)

    names, _ = zip(*iter(images))
    assert set(names) == {
        "bird1",
        "paint",
        "bird2",
        "mosaic",
        "castle",
        "church",
        "cliff",
    }


@pytest.mark.parametrize(
    ("name", "regions"),
    [
        ("castle", ("building", "water", "sky")),
        ("church", ("building", "sky")),
        ("cliff", ("water",)),
    ],
)
def test_images_guides_smoke(name, regions):
    image = demo.images()[name]

    assert isinstance(image.guides, data.DownloadableImageCollection)

    names, _ = zip(*iter(image.guides))
    assert set(names).issuperset(set(regions))


def test_transformer():
    torch.manual_seed(0)
    input_image = torch.rand(1, 3, 256, 256)
    transformer = demo.transformer()

    output_image = transformer(input_image)

    assert output_image.shape == input_image.shape
