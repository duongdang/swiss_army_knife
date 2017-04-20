#! /bin/bash

INPUTDIR=$1
OUTPUTPDF=$2

if [ -z "$INPUTDIR" -o -z "$OUTPUTPDF" ]; then
    echo "Usage $0 <INPUTDIR> <OUTPUTPDF>"
    exit 1
fi

TMPDIR=$(mktemp -d)
blank=$TMPDIR/a4.pdf
convert xc:none -page A4 $blank

files=""

while read f
do
    files="$files \"$f\""
    nbpages=$(pdfinfo "$f" | grep Pages | sed 's/[^0-9]*//')
    if ((nbpages % 2)); then
     	files="$files $blank"
    fi
done <<< "$(find "$INPUTDIR" -type f)"

eval pdftk $files cat output $OUTPUTPDF
