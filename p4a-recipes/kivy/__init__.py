"""Local override of python-for-android's kivy recipe.

Upstream declares:

    python_depends = ['certifi', 'chardet', 'idna', 'requests', 'urllib3', 'filetype']

`requests` pulls in charset-normalizer, which from 3.5.0 onward publishes PEP 738
Android wheels. python-for-android resolves requirements with

    pip install --dry-run --only-binary=:all: --platform=android_24_arm64_v8a ...

but then installs that resolved set with

    pip install --target ... --no-deps -r requirements.txt

with no --platform, so the host pip rejects the Android wheel it just chose:

    charset_normalizer-3.5.1-cp314-cp314-android_24_arm64_v8a.whl
    is not a supported wheel on this platform

Pinning charset-normalizer in buildozer.spec does not help: kivy's python_depends
are resolved in a different pip pass from the project's own requirements, so the
pin never constrains the pass that installs requests. Verified in build #5, which
pinned 3.4.5 and still resolved 3.5.0.

This app uses neither kivy.network.urlrequest nor kivy.garden, the only parts of
Kivy that need requests, so requests and the packages that exist solely to
support it are dropped. certifi and filetype are kept.

Remove this override once p4a passes --platform to its install step, or once
charset-normalizer's Android wheels install cleanly.
"""

from pythonforandroid.recipes.kivy import recipe as _upstream_recipe


class PatchedKivyRecipe(type(_upstream_recipe)):
    python_depends = ['certifi', 'filetype']


recipe = PatchedKivyRecipe()
