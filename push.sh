#!/usr/bin/env bash
# Deploy script! For pushmasters' eyes only.

# Step 0: Some awesome adjectives, names, and helper functions
adjectives=$(cat <<EOF
adorable
adventurous
aggressive
agreeable
alert
alive
amused
angry
annoyed
annoying
anxious
arrogant
ashamed
attractive
average
awful
bad
beautiful
better
bewildered
black
bloody
blue
blue-eyed
blushing
bored
brainy
brave
breakable
bright
busy
calm
careful
cautious
charming
cheerful
clean
clear
clever
cloudy
clumsy
colorful
combative
comfortable
concerned
condemned
confused
cooperative
courageous
crazy
creepy
crowded
cruel
curious
cute
dangerous
dark
dead
defeated
defiant
delightful
depressed
determined
different
difficult
disgusted
distinct
disturbed
dizzy
doubtful
drab
dull
eager
easy
elated
elegant
embarrassed
enchanting
encouraging
energetic
enthusiastic
envious
evil
excited
expensive
exuberant
fair
faithful
famous
fancy
fantastic
fierce
filthy
fine
foolish
fragile
frail
frantic
friendly
frightened
funny
gentle
gifted
glamorous
gleaming
glorious
good
gorgeous
graceful
grieving
grotesque
grumpy
handsome
happy
healthy
helpful
helpless
hilarious
homeless
homely
horrible
hungry
hurt
ill
important
impossible
inexpensive
innocent
inquisitive
itchy
jealous
jittery
jolly
joyous
kind
lazy
light
lively
lonely
long
lovely
lucky
magnificent
misty
modern
motionless
muddy
mushy
mysterious
nasty
naughty
nervous
nice
nutty
obedient
obnoxious
odd
old-fashioned
open
outrageous
outstanding
panicky
perfect
plain
pleasant
poised
poor
powerful
precious
prickly
proud
putrid
puzzled
quaint
real
relieved
repulsive
rich
scary
selfish
shiny
shy
silly
sleepy
smiling
smoggy
sore
sparkling
splendid
spotless
stormy
strange
stupid
successful
super
talented
tame
tasty
tender
tense
terrible
thankful
thoughtful
thoughtless
tired
tough
troubled
ugliest
ugly
uninterested
unsightly
unusual
upset
uptight
vast
victorious
vivacious
wandering
weary
wicked
wide-eyed
wild
witty
worried
worrisome
wrong
zany
zealous
EOF
)

scientists=$(cat <<EOF
aho
babbage
berners-lee
boole
borg
cantrill
carmack
curry
dijkstra
eich
gates
hamming
hennessy
hopper
huffman
joy
kernighan
kleene
knuth
lamport
lions
liskov
lovelace
matsumoto
mccarthy
mcilroy
moore
ng
norvig
ritchie
rivest
van-rossum
schneier
stallman
stroustrup
tanenbaum
thompson
torvalds
turing
ullman
viterbi
wozniak
EOF
)

_name() {
    echo $(echo "$adjectives" | shuf -n 1)-$(echo "$scientists" | shuf -n 1)
}

_yesno() {
    while true; do
        read -p "$1 (Y/n) " yn
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
        read -p "$1: " value
    else
        read -p "$1 [$2]: " value
        if [ -z "$value" ]; then
            value="$2"
        fi
    fi
    echo -n $value
}


HOST=medb@gluttony.local
ADMIN=stephen@gluttony.local
SERVICES="uwsgi@medb celery celerybeat"

# Step 1: Create git archive
TAGDESC="$(_getdefault "Tag message (no spaces)" "$(_name)")"
DATE="$(date +%Y-%m-%d)"
TAG="deploy-$DATE-$TAGDESC"

echo @@@ BUILD ARCHIVE @@@
git archive --format tar.gz -o medb-deploy.tar.gz HEAD

# Step 2: Send to host and create environment.
echo @@@ SEND ARCHIVE @@@
echo Destination: $HOST
scp medb-deploy.tar.gz $HOST: 2>/dev/null
PREV=$(ssh $HOST readlink current-ver 2>/dev/null | sed s@/@@)
echo @@@ SETUP ENV @@@
ssh $HOST "mkdir $TAG
cd $TAG
tar xf ../medb-deploy.tar.gz
python -m venv venv
venv/bin/pip install wheel
venv/bin/pip install -r requirements.txt
ln -s ../.env.secret .env.secret
sed -i 's/^MEDB_DEPLOY=.*$/MEDB_DEPLOY=$TAG/' .env
" 2>/dev/null

# Step 3: Down/up deploy, with optional pause for push plan
echo @@@ STOP OLD VERSION @@@
ssh $ADMIN "sudo systemctl stop $SERVICES" 2>/dev/null
echo
echo New environment is installed, and old version is stopped.
echo
echo Use this time to open another terminal and apply any migrations or manual
echo steps. Note that the old version is still symlinked at current-ver. You
echo can find the new version in $TAG
echo
if ! _yesno "Continue? (no will prematurely end push)"; then
    exit 1
fi
ssh $HOST "rm current-ver && ln -s $TAG current-ver" 2>/dev/null
ssh $ADMIN "sudo systemctl start $SERVICES" 2>/dev/null

# Step 4: Verify push and delete old version
echo
echo Push is completed, please verify.
echo
if ! _yesno "Certify?"; then
    echo @@@ ROLLBACK PUSH @@@
    ssh $ADMIN "sudo systemctl stop $SERVICES" 2>/dev/null
    ssh $HOST "rm current-ver && ln -s $PREV current-ver && rm -r $TAG" 2>/dev/null
    ssh $ADMIN "sudo systemctl start $SERVICES" 2>/dev/null
    echo @@@ ROLLBACK COMPLETE @@@
    exit 1
else
    git tag "$TAG"
    echo Certified $TAG
    ssh $HOST "rm -r $PREV" 2>/dev/null
    echo Removed old version $PREV
fi
