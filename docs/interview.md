# Interview walkthrough

## Honest introduction

“I built this AI-assisted, course-inspired implementation for my portfolio. Ed Donner's meeting-minutes exercise inspired the use case. I extended the workflow with source-linked items, a review interface, revision conflicts, persisted history and export controls. I can explain the code and its limitations.” Only claim personal design or implementation contributions you actually made and can demonstrate.

## Five-minute demonstration

1. Start the local server and load the fictional transcript without a key.
2. Show the suggestion about a later MySQL adapter: it is not an extracted action. Show Ravi's explicit commitment: it is.
3. Open an item's source. Explain that offline “summary” items are excerpts and optional AI only selects source IDs.
4. Edit a task, leave an unstated deadline blank, approve and save. Show the original quote is unchanged and the edit is labeled.
5. Download the action CSV and full JSON; explain why JSON includes excluded items and transcript data.
6. Open two tabs, save in one and attempt to save the old version in the other. Explain the 409 conflict and SQLite transaction.
7. Add a manual item and demonstrate that approval is cleared. Show revisions and delete the demo record.

## Questions to prepare

| Question | Explanation |
|---|---|
| Why not let the LLM write every field? | Selecting source IDs bounds generated claims; conservative server rules validate actions and decisions. It sacrifices recall and fluency. |
| Does a source link prove an item is true? | No. The source may be wrong, rules may misread wording and human edits may diverge. A link supports inspection. |
| Why SQLite? | A small local app needs transactions and persistent revisions without infrastructure. It is not the intended final multi-user architecture. |
| Why preserve “Friday”? | No meeting timezone/date is required, so calendar normalization would imply information we do not possess. |
| How do you test paid services? | Inject fake selectors/transcribers and mock provider contracts; live paid quality is not verified. |
| What would you improve? | Labeled evaluation transcripts with precision/recall, negation handling, authenticated ownership, provider-specific audio evaluation and retention controls. |

## Your next contribution

Run and understand the app, add your own permitted transcript, inspect failure cases, improve one conservative extraction rule and add a regression test. Record what changed and why. Replace generic claims on your CV with measured behavior you can reproduce. Avoid claiming live provider accuracy, business adoption or production scale without evidence.
