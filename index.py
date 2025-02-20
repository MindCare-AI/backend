def français_vers_python(chaine):
    for i in chaine:
        if i == ",":
            i = "."
    return chaine


français_vers_python("un,deux,trois")
