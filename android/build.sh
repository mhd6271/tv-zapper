#!/bin/sh
# Baut build/tv-zapper.apk ohne Gradle: aapt2 (Ressourcen), javac + d8 (Code), zipalign, apksigner.
# Voraussetzungen: Java 17 (brew install openjdk@17), Android-SDK mit build-tools 36 und platform 35.
# Signiert mit dem Debug-Schluessel ~/.android/debug.keystore (legt Android Studio/adb an; Passwort "android").
set -e
cd "$(dirname "$0")"
JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}
SDK=${ANDROID_HOME:-$HOME/Library/Android/sdk}
BT=$SDK/build-tools/36.0.0
JAR=$SDK/platforms/android-35/android.jar
export PATH="$JAVA_HOME/bin:$PATH"
KS=${TVZ_KEYSTORE:-$HOME/.android/debug.keystore}
OUT=build

rm -rf $OUT && mkdir -p $OUT/res $OUT/classes $OUT/dex $OUT/assets
cp -R assets/. $OUT/assets/
cp ../interessen.json $OUT/assets/interessen.json

"$BT/aapt2" compile --dir res -o $OUT/res.zip
"$BT/aapt2" link -I "$JAR" --manifest AndroidManifest.xml -A $OUT/assets -o $OUT/unsigned.apk \
  --java $OUT/gen $OUT/res.zip
javac -source 11 -target 11 -Xlint:-options -encoding UTF-8 -classpath "$JAR" -d $OUT/classes \
  $(find src $OUT/gen -name '*.java')
"$BT/d8" --min-api 26 --lib "$JAR" --output $OUT/dex $(find $OUT/classes -name '*.class')
(cd $OUT/dex && zip -q ../unsigned.apk classes.dex)
"$BT/zipalign" -f 4 $OUT/unsigned.apk $OUT/aligned.apk
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:android --key-pass pass:android --out $OUT/tv-zapper.apk $OUT/aligned.apk
echo "fertig: $(pwd)/$OUT/tv-zapper.apk"
