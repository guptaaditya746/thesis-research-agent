Write a short answer to the question, using only the numbered facts. Each sentence either states a finding and cites the facts it rests on, or says that no fact answers a part of the question. You do not add knowledge of your own.

Input:
- Question: the question to answer.
- Facts: the facts found in the papers, numbered from 1, one per line, as "[<number>] <paper> <fact>". A fact is one of three kinds:
  - a measured value: "<treatment> on <measure> (<higher or lower> is better): <value>, <dataset or group>. Quote: "<words of the paper>"";
  - what the authors say about their result: "The authors say: <direction>. Quote: "<words of the paper>"";
  - a claim of the paper: "<subject> <relation> <object> (<firm or hedged>). Quote: "<words of the paper>"".
  A "?" marks a part the paper does not give. "(higher is better)" or "(lower is better)" tells you which way is better on that measure.

Output fields:
- sentences: the answer, 1 to 8 sentences in reading order. Each entry has:
  - text: one sentence in plain words, without paper ids.
  - says: "finding" when the sentence states what the facts show; "cannot_tell" when it says that no fact answers a part of the question.
  - facts: the numbers of the facts the sentence rests on. A finding lists at least one; a cannot_tell sentence gives an empty list.

Example 1 (a normal case).
Input:
Question: Does Method K raise the Yield?

Facts:
[1] S901 Method K on Yield (higher is better): 0.45, no dataset named. Quote: "0.45"
[2] S901 Usual method on Yield (higher is better): 0.38, no dataset named. Quote: "0.38"
[3] S902 The authors say: improves. Quote: "Method K improves the Yield of every run."
Output:
{"sentences": [{"text": "Method K gave a higher Yield than the Usual method, 45% against 38%.", "says": "finding", "facts": [1, 2]}, {"text": "The authors of one study say Method K improves Yield.", "says": "finding", "facts": [3]}]}

Example 2 (a confusing case: lower is better, and a fact on another measure).
Input:
Question: Does Method P cut the Error count?

Facts:
[1] S901 Method P on Error count (lower is better): 15, no dataset named. Quote: "15"
[2] S901 Usual method on Error count (lower is better): 12, no dataset named. Quote: "12"
[3] S902 Method P on Yield (higher is better): 0.52, no dataset named. Quote: "0.52"
Output:
{"sentences": [{"text": "Method P gave more errors than the Usual method, 15 against 12.", "says": "finding", "facts": [1, 2]}]}
(On Error count lower is better, so 15 against 12 is the worse result for Method P. Fact 3 is on another measure, Yield, so it is not used.)

Example 3 (a missing case: no fact on one part of the question).
Input:
Question: How do Method K and the Usual method compare on Yield and on Error count?

Facts:
[1] S901 Method K on Yield (higher is better): 0.5, no dataset named. Quote: "0.50"
[2] S901 Usual method on Yield (higher is better): 0.5, no dataset named. Quote: "0.50"
Output:
{"sentences": [{"text": "Method K and the Usual method show no real difference in Yield, 0.50 against 0.50.", "says": "finding", "facts": [1, 2]}, {"text": "No fact here reports the Error count of Method K, so that part cannot be answered.", "says": "cannot_tell", "facts": []}]}

Rules (code checks the numbers, the fact lists, the paper ids and the length; a reply that breaks one is sent back once with the problems):
- Give 1 to 8 sentences, each at most 400 characters, each said once.
- Each finding names the treatments, measures and groups as the facts name them, and lists the numbers of the facts it rests on.
- Copy numbers from the cited facts only. Never compute a sum, mean, difference or percentage. A fraction and its percentage are the same number: 0.45 may be written 45%. A number written in the question (a year, a name with digits) may be repeated.
- Write a count of studies as a number no larger than the number of facts you cite, or in words.
- When facts disagree, say so and cite the facts of both sides.
- A part of the question that no fact speaks to gets one cannot_tell sentence with an empty list of facts.
- Leave paper ids such as S901 out of the text; the code adds them after each finding.
