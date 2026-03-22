Read the implementation plan at python/ast-docs/implementation-plan.md.
Implement Step 2. Follow the plan exactly — create the files listed in the
"Where" section, implement the code described in "How", and write all the
tests listed in "Tests". Run the tests and make sure they pass.
After implementation, verify that docstrings and comments match the code
as required by the root CLAUDE.md post-change review checklist.

# Refinement
In the plan document you mention "Validation milestone: After this step, preprocess all six sample .cob files and verify the output contains no sequence numbers, no comment lines, and no inline comments." - add a test that does this validation unless the test is already present