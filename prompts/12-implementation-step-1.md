Read the implementation plan at python/ast-docs/implementation-plan.md.
Implement Step 1. Follow the plan exactly — create the files listed in the
"Where" section, implement the code described in "How", and write all the
tests listed in "Tests". Run the tests and make sure they pass.
After implementation, verify that docstrings and comments match the code
as required by the root CLAUDE.md post-change review checklist.

# Reponse from Claude Code
  - Java wasn't installed on this machine, so I used the install-jdk Python package (a dependency of antlr4-tools) to install OpenJDK 11 to ~/.jdk/.           
  - The antlr4 CLI puts generated files in a subdirectory matching the grammar path — they were moved to generated/ as the plan requires.

# Refinement
1. Should we have install-jdk in the requirements-build.txt or not? do not be complacent, answer honestly and only based on what you certainly know.
2. You said "The antlr4 CLI puts generated files in a subdirectory matching the grammar path — they were moved to generated/ as the plan requires." - is it more correct to follow the plan instructions or to keep the default used by antlr4 CLI?