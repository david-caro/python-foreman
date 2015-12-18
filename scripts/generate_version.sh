#!/bin/bash -e
# This script generates the version string from the git repo
#
# Greatly inspired on pbr, but without forcing dev snapshot versions
#
# It allows to bump the major version on commits that have a sem-ver header
# with the break word in it, for example:
#
#     sem-ver: api-breaking
#     sem-ver: compat-breaking
#     sem-ver: breaks compatibility
#     sem-ver: api-breaking
#
# That will force a major version bump even if there's no tag
#
# And bumping the middle version adding a header:
#
#     sem-ver: feature
#
# It always generates a 3 elements version minimum (X.Y.Z)
#
# It does not count commits hidden behind a merge commit (follows only the
# first parent of the merge commit)
#
GIT_LOG='git log --first-parent'
# This is to avoid matchin with any string in the commit message
COMMIT_HEADER='123456789012345678901234567890123456789012345678901234567890123'


get_last_valid_tag() {
    git tag \
    | grep -e '^[0-9]\+\.[0-9]\+$' \
    | xargs -I@ git log --format=format:"%ai @%n" -1 @ \
    | sort \
    | tail -n1 \
    | awk '{print $4}'
    return 0
}


get_non_backwards_compatible_changes_count_since() {
    local since="${1?}"
    $GIT_LOG --pretty=format:%b "$since"..HEAD \
    | grep -i -c -e '^sem-ver: .*break.*'
    return 0
}


get_last_non_backwards_compatible_change_since() {
    local since="${1?}"
    $GIT_LOG \
        "--pretty=format:$COMMIT_HEADER:%h%n%b" \
        "$since"..HEAD \
    | grep -i -e "\(^$COMMIT_HEADER:\|^sem-ver: .*break.*\)" \
    | grep -B1 -i -e '^sem-ver: .*break.*' \
    | head -n1 \
    | cut -d':' -f2
    return 0
}


get_feature_changes_count_since() {
    local since="${1?}"
    $GIT_LOG --pretty=format:%b "$since"..HEAD \
    | grep -i -c -e '^sem-ver: feature'
    return 0
}

get_last_feature_change_since() {
    local since="${1?}"
    $GIT_LOG \
        "--pretty=format:$COMMIT_HEADER:%h%n%b" \
        "$since"..HEAD \
    | grep -i -e "\(^$COMMIT_HEADER:\|^sem-ver: \(.*break.*\|feature\)\)" \
    | grep -B1 -i -e '^sem-ver: \(.*break.*\|feature\)' \
    | head -n1 \
    | cut -d':' -f2
    return 0
}


get_commit_count_since() {
    local since="${1?}"
    $GIT_LOG --oneline \
        "$since"..HEAD \
    | wc -l
    return 0
}


get_current_version() {
    local tag_major_ver \
        cur_min_ver \
        cur_major_ver \
        prev_tag \
        since_tag_major_changes

    prev_tag="$(get_last_valid_tag)"
    maj_version="${prev_tag%.*}"
    middle_version="${prev_tag#*.}"

    last_major="$(get_last_non_backwards_compatible_change_since "$prev_tag")"
    if [[ "$last_major" == "" ]]; then
        last_major="$prev_tag"
    else
        middle_version=0
    fi

    last_feat="$(get_last_feature_change_since "$last_major")"
    if [[ "$last_feat" == "" ]]; then
        last_feat="$last_major"
    fi

    majors_since_tag="$( \
        get_non_backwards_compatible_changes_count_since "$prev_tag" \
    )"
    feats_since_major="$(get_feature_changes_count_since "$last_major")"
    bugs_since_feat="$(get_commit_count_since "$last_feat")"

    cur_major_ver="$(($maj_version + $majors_since_tag))"
    cur_middle_ver="$(($middle_version + $feats_since_major))"
    cur_min_ver="$bugs_since_feat"
    echo "$cur_major_ver.$cur_middle_ver.$cur_min_ver"
}


if ! [[ "$0" =~ .*/bash ]]; then
    get_current_version
fi

