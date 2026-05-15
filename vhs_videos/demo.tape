# VHS tape for the local-first ingest demo.
#
# Render with `vhs vhs_videos/demo.tape` after installing docmancer
# (pipx install docmancer) and after `docmancer setup` has been run
# once so the user config exists.
#
# Total runtime target: under 90 seconds.

Output vhs_videos/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1100
Set Height 640
Set Theme "Dracula"
Set TypingSpeed 35ms
Set PlaybackSpeed 1.0

Type "# 1. Install once."
Enter
Sleep 600ms
Type "pipx install docmancer --python python3.13"
Sleep 800ms
Enter
Sleep 1500ms

Type "# 2. Point at any folder of docs."
Enter
Sleep 600ms
Type "docmancer ingest ./test-corpora/stories-md"
Enter
Sleep 2500ms

Type "# 3. Ask questions that hit a specific chapter."
Enter
Sleep 600ms
Type 'docmancer query "the Mad Hatter tea party"'
Enter
Sleep 2200ms

Type 'docmancer query "Sherlock Holmes and a snake" --mode hybrid --explain'
Enter
Sleep 2200ms

Type "# 4. Inspect what is indexed."
Enter
Sleep 500ms
Type "docmancer inspect"
Enter
Sleep 1800ms

Type "# 5. Install a skill so your agent can call this directly."
Enter
Sleep 500ms
Type "docmancer install claude-code"
Enter
Sleep 1800ms
