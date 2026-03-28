#!/usr/bin/bash
# Deploy script!

# Push destination details
REGISTRY="reg.vps.brenns10.com"
HOST=stephen@gluttony
SERVICES="medb-web.service medb-worker.service"

_name() {
    local rev dirty
    rev="$(git rev-parse --short HEAD)"
    dirty=""
    if ! git diff-index --quiet --cached HEAD; then
        dirty="+dirty"
    elif ! git diff-files --quiet; then
        # Working tree has changes.
        dirty="+dirty"
    elif [ -n "$(git ls-files --others --exclude-standard)" ]; then
        dirty="+dirty"
    fi
    echo "$rev$dirty"
}

_yesno() {
    while true; do
        read -rp "$1 (Y/n) " yn
        case $yn in
                "" ) break;;
                [Yy]* ) break;;
                [Nn]* ) return 1;;
                * ) echo "Please answer yes or no.";;
        esac
    done
}

_getdefault() {
    if [ -z "$2" ]; then
        read -rp "$1: " value
    else
        read -rp "$1 [$2]: " value
        if [ -z "$value" ]; then
            value="$2"
        fi
    fi
    echo -n "$value"
}

TAGDESC="$(_getdefault "Tag message (no spaces)" "$(_name)")"
DATE="$(date +%Y-%m-%d)"
TAG="deploy-$DATE-$TAGDESC"

echo @@@ BUILD IMAGE @@@
podman build --build-arg MEDB_DEPLOY="$TAG" -t medb:latest .

echo @@@ PUSH IMAGE @@@
podman push medb:latest "$REGISTRY/medb:latest"

echo @@@ STOP OLD VERSION @@@
ssh $HOST "systemctl --user stop $SERVICES"
echo
echo The new image has been pushed and the old services stopped.
echo
echo Use this time to open another terminal and apply any migrations or manual
echo steps. The new image should be tagged \"medb:latest\" while the old one
echo should be retained as \"medb:stable\".
echo
if ! _yesno "Continue? (answering no will require cleanup)"; then
    exit 1
fi
ssh $HOST "systemctl --user start $SERVICES"

# Step 4: Verify push and delete old version
echo
echo Push is completed, please verify.
echo
if ! _yesno "Certify?"; then
    echo @@@ ROLLBACK PUSH @@@
    skopeo copy docker://$REGISTRY/medb:{stable,latest}
    ssh $HOST "systemctl --user restart $SERVICES" 2>/dev/null
    echo @@@ ROLLBACK COMPLETE @@@
    exit 1
else
    skopeo copy docker://$REGISTRY/medb:{latest,stable}
    echo Certified $TAG
fi
