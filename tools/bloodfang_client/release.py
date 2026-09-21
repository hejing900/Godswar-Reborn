"""Reviewed Bloodfang v6 presentation scale; model and artwork stay unchanged."""
from pathlib import Path

PATCH_ID = 'reborn.bloodfang-species46.v6'
ASSET_DIRECTORY = Path(__file__).resolve().parents[2] / 'assets/bloodfang/native'
ASSET_HASHES = {
    'Bloodfang_male_001.jcs': '2a9276ed42b191a70b554a304afe89195add643fde3f2d8d4f35ff526eb7b7df',
    'Bloodfang_male_001.gwo': 'afa6e9b228320db15c780aa20531b88ecb2e2306ef7e7abf1724b0823f3fe292',
}
PORTRAIT_FILENAME = 'bloodfang-portrait.png'
PORTRAIT_SHA256 = 'dd7ad9cf14863cd63318130be8a4d1023a99137a6aff23685a275b9e7f5daf4c'
# Native Wonderland dragon, unchanged geometry and facing. The pet is 50%
# larger than v5, still well below the boss's 3.0 scale. Bounds cover all 92 poses.
MODEL_PROFILE = dict(NameHeight='2.2', Range='1.0f', Shadow='0.8f',
                     Scale0='0.525f', ScaleOther='0.5775f', AabbMinX='-9.6',
                     AabbMaxX='9.9', AabbMinY='-2.2', AabbMaxY='8.6',
                     AabbMinZ='-9.4', AabbMaxZ='6.3')
