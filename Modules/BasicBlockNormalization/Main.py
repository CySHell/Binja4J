

def normalize_vars():

    "MATCH(var: Variable) WHERE"
    "var.SourceVarType = 'FlagVariableSourceType'"
    "SET var.NormalizedVarType = 'FLAG'"

    "MATCH(var: Variable) WHERE"
    "var.SourceVarType = 'StackVariableSourceType'"
    "SET var.NormalizedVarType = 'STACK'"

    "MATCH(var: Variable) WHERE"
    "var.SourceVarType = 'RegisterVariableSourceType'"
    "SET var.NormalizedVarType = 'REG'"