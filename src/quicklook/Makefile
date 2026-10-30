# Sprite QuickLook: build, test and install the host app and its QuickLook extensions
# (see README.md). DerivedData stays out of Dropbox.

DERIVED_DATA := $(HOME)/Library/Developer/Xcode/DerivedData/SpritePreview
BUILT_APP := $(DERIVED_DATA)/Build/Products/Release/GlitchyGames Sprite Preview.app
INSTALLED_APP := /Applications/GlitchyGames Sprite Preview.app
LSREGISTER := /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

.PHONY: test project build install uninstall

test:
	swift test

project:
	xcodegen --spec App/project.yml

build: project
	xcodebuild -project App/SpritePreview.xcodeproj -scheme SpritePreview -configuration Release \
		-derivedDataPath "$(DERIVED_DATA)" build

install: build
	rm -rf "$(INSTALLED_APP)"
	cp -R "$(BUILT_APP)" "$(INSTALLED_APP)"
	# Only the installed copy should provide the extensions: forget the build product, which
	# Xcode's build registers, then register the installed app (opening it once does too).
	# The build product is deleted too: left on disk it got registered again and showed up in
	# System Settings as a second app with "0 extensions installed" (2026-10-29). The next
	# build makes it again from the cached objects.
	$(LSREGISTER) -u "$(BUILT_APP)"
	rm -rf "$(BUILT_APP)"
	$(LSREGISTER) -f "$(INSTALLED_APP)"
	pluginkit -a "$(INSTALLED_APP)/Contents/PlugIns/"*.appex
	open "$(INSTALLED_APP)"
	qlmanage -r
	qlmanage -r cache

uninstall:
	-pluginkit -r "$(INSTALLED_APP)/Contents/PlugIns/"*.appex
	-$(LSREGISTER) -u "$(INSTALLED_APP)"
	rm -rf "$(INSTALLED_APP)"
	qlmanage -r
	qlmanage -r cache
