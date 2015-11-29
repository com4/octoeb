_octoeb_completion() {
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \
                   COMP_CWORD=$COMP_CWORD \
                   _OCTOEB_COMPLETE=complete $1 ) )
    return 0
}

complete -F _octoeb_completion -o default octoeb;
