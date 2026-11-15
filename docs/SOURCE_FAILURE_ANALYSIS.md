# Source failure analysis

Read-only analysis of the already exposed 48-question test. No gold answers or scores were changed. These are evidence-backed engineering hypotheses, not independently reviewed semantic judgments.

## new_failure: squad-57112686b654c5140001fbd3

Along with geothermal and nuclear, what is a notable non-combustion heat source?

Published answers: ["solar", "solar power", "solar power, nuclear power or geothermal energy"]
Baseline: Solar power
SourceROI: geothermal

Assessment: **context_filtering**. The 512-character whole-chunk filter discarded the relevant Steam_engine passage and retained an unrelated short passage. The published solar answer disappeared. This supports a context-selection failure, not failure of the source corpus.

Baseline passages (4/4 full reference quotes):

- Steam_engine — `squad::8c113acd4fdc7912bf842ccff23fb13d856b38b4a9059a4e811662a2c5710431.txt#chunk0`
- Enrico Fermi — `hotpot::90dd76a0e1bd0200801181da8e3907c3953f9e282d09af9e4098ae3d96e8650c.txt#chunk0`
- Claudio Pellegrini — `hotpot::82c548f6664b1b68e4f631acc9f370e3344f94b9f531250382e5fb05436424ce.txt#chunk0`
- Geology — `squad::e71c68a449b4204d19cd3c8094c3921c3104ec8434af9f04cf0c64c1219bbc5a.txt#chunk0`
- Claudio Pellegrini — `hotpot::82c548f6664b1b68e4f631acc9f370e3344f94b9f531250382e5fb05436424ce.txt#chunk1`

Candidate passages (0/4 full reference quotes):

- Claudio Pellegrini — `hotpot::82c548f6664b1b68e4f631acc9f370e3344f94b9f531250382e5fb05436424ce.txt#chunk1`

## new_failure: squad-5725d34089a1e219009abf51

What did Distributed Adaptive Message Block Switching do

Published answers: ["provide a fault-tolerant, efficient routing method for telecommunication messages", "fault-tolerant, efficient routing method"]
Baseline: provide a fault-tolerant, efficient routing method for telecommunication messages
SourceROI: Provided a fault-tolerant, efficient routing method for telecommunication messages

Assessment: **scoring_ambiguity**. The complete reference passage remains supplied. The answer differs as “Provided” versus published “provide”. This is plausibly semantically equivalent; keep the exact-match failure unchanged and flag independent review. There is no evidence of missing information.

Baseline passages (3/3 full reference quotes):

- Packet_switching — `squad::96b9416fc7950c15dd77956d56285794674c15ef635ed948923885cdbae1decc.txt#chunk0`
- All I Wanna Do Is Make Love to You — `hotpot::c2370ea67bd786809f26b4192143e6700af80b64d0d5726e6e2a1007b0d47543.txt#chunk0`
- Silene — `hotpot::a6be1b5454b37b688997bd2a9be1408511e9509ea58190197a41224d635c3056.txt#chunk0`
- Nutri Ventures – The Quest for the 7 Kingdoms — `hotpot::b20925f52b336156741f16913b64dd21bc9618d4b43fa654e780521d0b368af6.txt#chunk0`
- Richard Nixon — `hotpot::66ccbe6782376f1fd6926f620934a94e3fc0d68ec4a4c5ef7335b3852b574b84.txt#chunk0`

Candidate passages (3/3 full reference quotes):

- Packet_switching — `squad::96b9416fc7950c15dd77956d56285794674c15ef635ed948923885cdbae1decc.txt#chunk0`
- All I Wanna Do Is Make Love to You — `hotpot::c2370ea67bd786809f26b4192143e6700af80b64d0d5726e6e2a1007b0d47543.txt#chunk0`
- Black_Death — `squad::5ff5f51a1cc51906b646d6d26839d7263ae36b42e13455ce7fa04282a3e318d1.txt#chunk0`

## new_failure: hotpot-5a8db19d5542994ba4e3dd00

Are Local H and For Against both from the United States?

Published answers: ["yes"]
Baseline: Yes
SourceROI: INSUFFICIENT_EVIDENCE

Assessment: **empty_context_and_baseline_support_incomplete**. The 128-character filter removed every chunk. The baseline contained For Against but not the annotated Local H passage. Removal of available support is observed; the baseline yes answer is not proven fully grounded, and prior knowledge may contribute.

Baseline passages (1/2 full reference quotes):

- For Against — `hotpot::b768f41a29e93650a87a562102844badb5285a6292e9f802cfb3c7c57c144518.txt#chunk0`
- Amherst, Massachusetts — `hotpot::845cd20ee97b0d9ee2bac535b401f2d85876fd00e5ecc1711db28b7a1700992e.txt#chunk0`
- NetSupport Manager — `hotpot::3e24aba51deffe739379e4ad388ef63603295170806c352d74c244350a76520f.txt#chunk1`
- United States Senate election in Illinois, 1978 — `hotpot::d02a0f33abbdf3fb9930bc2d72b9ba0d2280723a646bf48a9f714231dea8194d.txt#chunk0`
- Gerald Ford — `hotpot::69990d88efdc6a76c2ea219891bfeaf48026e40e0eaa84dad49b5e12551599bc.txt#chunk0`

Candidate passages (0/2 full reference quotes):

- No context supplied.

## new_failure: hotpot-5ab859a955429934fafe6d7b

Who is the writer of this song that was inspired by words on a tombstone and was the first track on the box set Back to Mono?

Published answers: ["Phil Spector"]
Baseline: Phil Spector
SourceROI: Bob Dylan

Assessment: **empty_context**. The baseline supplied the box-set and song passages with all supporting facts. The 512-character filter discarded every chunk; Bob Dylan replaced the supported Phil Spector answer. This supports destructive filtering followed by unsupported generation.

Baseline passages (3/3 full reference quotes):

- Back to Mono (1958–1969) — `hotpot::70f17b9eaaed187c59dc49062be923573ae102be5d65cacf11cce52e34350e6c.txt#chunk0`
- Mono Masters — `hotpot::f5b2c9f69f1bb84101f848a7432cc70f35e016568ca7014eef4785b20a880c60.txt#chunk0`
- To Know Him Is to Love Him — `hotpot::fbd51b467da755eb7d23d6e2a1434cb19f5bbd83355f2207ac524d9fe2d0267a.txt#chunk0`
- Led Zeppelin Boxed Set 2 — `hotpot::2fca066ef6a78c6b044d29bc6b767954fd501dd881ffad066b11ff0479eee342.txt#chunk0`
- The Doors: Vinyl Box Set — `hotpot::4cf2de725c17e44607b1655a74d44d74583473befd8dd34a4eb93b4c2870b778.txt#chunk0`

Candidate passages (0/3 full reference quotes):

- No context supplied.

## recovery: squad-57271c235951b619008f860c

What is an example of major civil disobedience in South Africa?

Published answers: ["apartheid", "fight against apartheid", "the fight against apartheid", "Singing Revolution to bring independence to the Baltic countries"]
Baseline: The 1919 Revolution
SourceROI: The fight against apartheid

Assessment: **generation_or_distractor_sensitivity_uncertain**. Both configurations supplied the apartheid passage. The selected distractors changed and the response became correct. Reduced distraction is plausible, but attention/reasoning variation is not established causally without a controlled follow-up.

Baseline passages (5/5 full reference quotes):

- Civil_disobedience — `squad::2fe5f932a9441233c7ec8f01256234553c10079b298e1908a75aacdc0fe4addb.txt#chunk0`
- Battle of Romanovka — `hotpot::570af19ec307fd92e3c854102a58cbf4423ecf16ef825b2c2f8b770fc22c9375.txt#chunk0`
- South West Pacific theatre of World War II — `hotpot::137ef962caa4787fbc8cb2f14f020eba7c0e6bd198afacdead1292d94ebc76a7.txt#chunk0`
- South West Pacific Area (command) — `hotpot::8eaa3562e3d9079e4fbc78583b223172c7342b89f8c87e3db6c545ffd78ff99d.txt#chunk0`
- Huernia — `hotpot::2977f063bc06658d40730fd9b82a98423177254c58e08cd29263697a73ee851b.txt#chunk0`

Candidate passages (5/5 full reference quotes):

- Civil_disobedience — `squad::2fe5f932a9441233c7ec8f01256234553c10079b298e1908a75aacdc0fe4addb.txt#chunk0`
- Pre-Commissioning Unit — `hotpot::2e042a3f30f8a79c3350c311b7b42aaa23686d45c0b050fe7a46193f873ec84e.txt#chunk0`
- John Roach &amp; Sons — `hotpot::ef4e5b8a9c801220436144e6668de1a5c53eff8d75b7386cd70a15ee1638369f.txt#chunk0`

## recovery: hotpot-5a8e068b5542995085b37384

Are Ferocactus and Silene both types of plant?

Published answers: ["yes"]
Baseline: No
SourceROI: yes

Assessment: **correct_without_evidence**. The new policy supplied no context yet returned yes. This is a reference-score recovery without supplied support, not evidence-selection success. Prior knowledge, question clues or guessing cannot be distinguished here.

Baseline passages (0/2 full reference quotes):

- Silene menziesii — `hotpot::839f826a22df535bd2bf9a2d8c1b3ac0eaf96b195e12a9ff7edb981663ef444e.txt#chunk1`
- Silene menziesii — `hotpot::839f826a22df535bd2bf9a2d8c1b3ac0eaf96b195e12a9ff7edb981663ef444e.txt#chunk0`
- Silene latifolia — `hotpot::2e0e5632872d2fcf8e7da1d221d883e6ef42eec5fc33692adb4dc12926e2337e.txt#chunk0`
- Silene stenophylla — `hotpot::532913b7b1440c59c5adb942730d0235646545661456c2fd8d619871e3022076.txt#chunk0`
- Silene tomentosa — `hotpot::922b0e02c5dcbbd8851430da87ba6a9f76ebb88424d888d06f70f9aabb9430bd.txt#chunk0`

Candidate passages (0/2 full reference quotes):

- No context supplied.

## recovery: hotpot-5ab84bf555429916710eb01f

In 1991 Euromarché was bought by a chain that operated how any hypermarkets at the end of 2016?

Published answers: ["1,462"]
Baseline: Tazweed Center
SourceROI: 1,462

Assessment: **complementary_evidence_retrieved**. Coverage selection restored both Euromarché and Carrefour, which the baseline missed. Both published supporting articles are now present and the answer becomes correct. This supports a useful ranking/coverage association; it is not a universal causal source-importance score.

Baseline passages (0/2 full reference quotes):

- Uno-X — `hotpot::3ac4cb333abe2634e8bcceeb21ac99b9e87774ba8f109ec372b8e328b23888d4.txt#chunk0`
- Lewis's — `hotpot::6d60c0331045ed425564c3bec0732d4b2e09e8b0fa223787de0c654d687a30df.txt#chunk0`
- Tesco Extra — `hotpot::25c9ad0dd339a322d993d667f749168f12ceb0ff8b53ce89b0387119e6d5cd7e.txt#chunk0`
- Tazweed Center — `hotpot::6ad5bac3c30fb093a026d7abbc1d914e932d79f409eb70552803a597b7906d53.txt#chunk0`
- Selver — `hotpot::2ed492001ef7abb3cb795f60dba7c9b488e148da5758c566546d37ac3c25f8af.txt#chunk0`

Candidate passages (2/2 full reference quotes):

- Lewis's — `hotpot::6d60c0331045ed425564c3bec0732d4b2e09e8b0fa223787de0c654d687a30df.txt#chunk0`
- Carrefour — `hotpot::7033c53d43fde50be207d0d4da395fce887b4986079f932f8b36406ec4d2d089.txt#chunk0`
- Euromarché — `hotpot::25602629bcbbfc0d786fd60809b8c89f2331e2cb0bb5c108dc210a725a9b3360.txt#chunk0`
- Uno-X — `hotpot::3ac4cb333abe2634e8bcceeb21ac99b9e87774ba8f109ec372b8e328b23888d4.txt#chunk0`
- Tesco Extra — `hotpot::25c9ad0dd339a322d993d667f749168f12ceb0ff8b53ce89b0387119e6d5cd7e.txt#chunk0`

## Implications

Three exact-score losses involve destructive context filtering; one has a plausible tense-only scoring ambiguity. Two recoveries have supplied reference evidence, while one was generated with no context. Do not claim all failures were missing-information failures or all recoveries were grounded.

New policies and baselines must be frozen and tested on new document-disjoint questions. The old cases may be regression tests, never a fresh final test.
