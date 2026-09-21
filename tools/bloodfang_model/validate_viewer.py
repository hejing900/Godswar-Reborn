"""Exercise the packaged local WebGL viewer in an isolated headless browser."""
import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def validate(path, screenshot):
    errors = []
    with sync_playwright() as runner:
        browser = runner.chromium.launch(channel='msedge', headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 900},
                                    reduced_motion='reduce')
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(path.resolve().as_uri())
            page.wait_for_function('window.BLOODFANG_VIEWER?.ready')
            textured = page.evaluate('Boolean(window.BLOODFANG_MODEL.texture)')
            if textured:
                page.wait_for_function('window.BLOODFANG_VIEWER.textureReady === true')
            clips = page.locator('#clip option').count()
            poses = []
            for index in range(clips):
                page.select_option('#clip', str(index))
                page.locator('#timeline').evaluate("e => {e.value=450;e.dispatchEvent(new Event('input'));}")
                page.evaluate('window.BLOODFANG_VIEWER.renderCurrentFrame()')
                image = page.locator('#model').screenshot()
                poses.append(hashlib.sha256(image).hexdigest())
            page.select_option('#clip', '0')
            page.locator('#timeline').evaluate("e => {e.value=0;e.dispatchEvent(new Event('input'));}")
            page.locator('#reset').click()
            page.evaluate('window.BLOODFANG_VIEWER.renderCurrentFrame()')
            before = page.locator('#model').screenshot()
            page.locator('#model').press('ArrowRight')
            page.evaluate('window.BLOODFANG_VIEWER.renderCurrentFrame()')
            rotated = page.locator('#model').screenshot() != before
            page.locator('#reset').click()
            page.evaluate('window.BLOODFANG_VIEWER.renderCurrentFrame()')
            reset = page.locator('#model').screenshot() == before
            page.locator('#model').press('+')
            page.evaluate('window.BLOODFANG_VIEWER.renderCurrentFrame()')
            zoomed = page.locator('#model').screenshot() != before
            page.locator('#reset').click()
            page.locator('#play').click()
            playing = page.locator('#play').get_attribute('aria-pressed') == 'true'
            page.locator('#play').click()
            paused = page.locator('#play').get_attribute('aria-pressed') == 'false'
            gl_error = page.evaluate("document.getElementById('model').getContext('webgl').getError()")
            if screenshot:
                page.screenshot(path=str(screenshot), full_page=True)
            result = dict(animations=clips, distinctPoseImages=len(set(poses)),
                          textureLoaded=textured, rotation=rotated, reset=reset,
                          zoom=zoomed, playPause=playing and paused,
                          webglError=gl_error, errors=errors)
            result['passed'] = (clips == len(set(poses)) == 6 and rotated and reset and zoomed
                                and playing and paused and gl_error == 0 and not errors)
            return result
        finally:
            browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('viewer', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    result = validate(args.viewer, args.screenshot)
    args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
