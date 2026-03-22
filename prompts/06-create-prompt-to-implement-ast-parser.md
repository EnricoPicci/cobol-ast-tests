# Role
You are a Claude Code maverick and you know how to create the best and more effective prompts for Claude Code.

# Context
You want to ask Claude Code to help you plan the implementation a Cobol AST parser in Python. 
The first draft of the prompt you have written is shown below in <PROMPT-DRAFT>

# Task
Review <PROMPT-DRAFT>, explain what has to be improved and write in the file `prompts/07-plan-implementation-python-ast-parser` the best prompt to use for this purpose.

<PROMPT-DRAFT>
# Role
You are a Python maverick.
You also know very well Cobol and AST Parsers.

# Context
You work in this project that has the goal to create educational examples on how to use Cobol AST parsers to analyze and change Cobol source code.
The Cobol AST parsers have to be able to read Cobol Microfocus for IBM AIX sources and IBM Cobol for Linux sources.
You have analyzed the possible ways to create a Cobol AST parser and you have written your findings in the document `python/ast-docs/parser-evaluation.md`.
As a result of the analysis you have opted to create a parser based on "ANTLR4 + Cobol85.g4".
You have already created a Cobol AST parser using this technology and the code is in the repo `https://github.com/EnricoPicci/cobol-ast-parser/tree/main`. You may take inspiration from this project but you have never to cite it since the current project you are working in is a totally different task.
Now you want to create a new implementation of the parser for this project.
You have access to some Cobol Microfocus examples in the subfolders of the folder `samples`. 

# Task
You have to document the implementation plan for this Python AST parser for Cobol
The plan has to be save in a document in the folder `python/ast-docs`.
I may decide to implement the plan either step by step or few steps at a time or all plan in one shot. Each step or block of steps implemented together has to some tests that allow me to understand better what has been created.
The plan has to be clear enough to represent the documentation of what each step does, so there is no need to create any further documentation at the end of the implementation of each step.
<PROMPT-DRAFT/>