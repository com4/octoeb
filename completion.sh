_octoeb_completion() {
    local cur prev
    cur=${COMP_WORDS[COMP_CWORD]}
    prev=${COMP_WORDS[COMP_CWORD-1]}

    case ${COMP_CWORD} in
        1)
            COMPREPLY=($(compgen -W "start review qa release jira method sync update changelog" ${cur}))
            ;;
        2)
            case ${prev} in
                start)
                    COMPREPLY=($(compgen -W "feature hotfix releasefix release" ${cur}))
                    ;;
                review)
                    COMPREPLY=($(compgen -W "feature hotfix releasefix flake8" ${cur}))
                    ;;
                qa)
                    COMPREPLY=($(compgen -W "-v" ${cur}))
                    ;;
                release)
                    COMPREPLY=($(compgen -W "-v" ${cur}))
                    ;;
                jira)
                    COMPREPLY=()
                    ;;
                method)
                    COMPREPLY=()
                    ;;
                esac
                ;;
        3)
            case ${prev} in
                feature|hotfix|releasefix)
                    COMPREPLY=($(compgen -W "-t" ${cur}))
                    ;;
                flake8)
                    COMPREPLY=($(compgen -W "-b" ${cur}))
                    ;;
                *)
                    COMPREPLY=()
                    ;;
                esac
                ;;
        4)
            tickets=$(octoeb jira -m get_my_ticket_ids)
            COMPREPLY=($(compgen -W "${tickets}" ${cur}))
            ;;
        *)
            COMPREPLY=()
            ;;
        esac
}

complete -F _octoeb_completion -o default octoeb;
