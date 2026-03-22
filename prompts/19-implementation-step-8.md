Read the implementation plan at python/ast-docs/implementation-plan.md.
Implement Step 8. Follow the plan exactly — create the files listed in the
"Where" section, implement the code described in "How", and write all the
tests listed in "Tests". Run the tests and make sure they pass.
After implementation, verify that docstrings and comments match the code
as required by the root CLAUDE.md post-change review checklist.

# Answer from Claude
  One notable discovery: the ANTLR4 Cobol85 grammar expects EXEC SQL blocks to be pre-tagged with *>EXECSQL prefixes (each line becomes an
   EXECSQLLINE token). The current preprocessor doesn't perform this tagging yet — this will need to be addressed when integrating the    
  full pipeline in Step 9.   

# My note
I wait for the next step to fix the issue, as already suggested by Claude