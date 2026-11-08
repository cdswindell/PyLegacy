#!/usr/bin/env bash
#
# Provide hostname replacement for Steam Deck
#
case "${1:-}" in
    -I|--all-ip-addresses)
        /usr/bin/ip -o -4 address show scope global |
            /usr/bin/awk '{
                sub(/\/.*/, "", $4)
                printf "%s ", $4
            }
            END {
                print ""
            }'
        ;;
    *)
        /usr/bin/uname -n
        ;;
esac
