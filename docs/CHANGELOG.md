# CHANGELOG

<!-- version list -->

## v4.0.0 (2026-11-18)

### Bug Fixes

- Colorbar() label uses the heatmap's own axes
  ([`3bc52b3`](https://github.com/BenHuddart/gleplot/commit/3bc52b33e9fef3476cc5f91c019428dda71e9a0f))

### Features

- Closed-form fits with Axes.fit(model=...) ([#75](https://github.com/BenHuddart/gleplot/pull/75),
  [`263b48d`](https://github.com/BenHuddart/gleplot/commit/263b48d9bbc7cbe368f851255e5e9166178f5071))

- Colorbar per axes and horizontal colorbars ([#78](https://github.com/BenHuddart/gleplot/pull/78),
  [`a882209`](https://github.com/BenHuddart/gleplot/commit/a882209bbb59e7266e958196ae39d505fe250415))

- Hatch patterns on bars ([#71](https://github.com/BenHuddart/gleplot/pull/71),
  [`232b7ca`](https://github.com/BenHuddart/gleplot/commit/232b7ca2d60229ce0f2b6fd20a18dc7acf970e84))

- LaTeX-rendered labels with GLEStyleConfig(usetex=True)
  ([#72](https://github.com/BenHuddart/gleplot/pull/72),
  [`34e3ca4`](https://github.com/BenHuddart/gleplot/commit/34e3ca4ecd652832749e7a011ec1cc3047319926))


## v3.19.0 (2026-11-18)

### Features

- Clip box plots to the frame, review fixes for boxplot
  ([#57](https://github.com/BenHuddart/gleplot/pull/57),
  [`6aa1634`](https://github.com/BenHuddart/gleplot/commit/6aa1634725b5c3b4d98b2d510a7e69b1672264d6))

- Legend bbox_to_anchor, spacing keywords and labelcolor
  ([#87](https://github.com/BenHuddart/gleplot/pull/87),
  [`957f957`](https://github.com/BenHuddart/gleplot/commit/957f9579e785282b09150242848f3b622f03b30b))

- Tick marks, minor ticks and log sub-labels ([#73](https://github.com/BenHuddart/gleplot/pull/73),
  [`047e1ef`](https://github.com/BenHuddart/gleplot/commit/047e1ef5e6ed421daf9766e0f06c0913459f9855))

- Vertical box plots with Axes.boxplot and glp.boxplot
  ([#57](https://github.com/BenHuddart/gleplot/pull/57),
  [`a8fe0b5`](https://github.com/BenHuddart/gleplot/commit/a8fe0b582100f75dc8a449929314349784a172c2))

### Testing

- Pin round trip of hand-written custom marker definitions
  ([`724180b`](https://github.com/BenHuddart/gleplot/commit/724180ba0c6df53c3dded130fa2f06af62661337))


## v3.18.0 (2026-11-18)

### Features

- Axes through the origin with Axes.set_math_mode
  ([#74](https://github.com/BenHuddart/gleplot/pull/74),
  [`0a1163b`](https://github.com/BenHuddart/gleplot/commit/0a1163be0a81e7e423ae956defaf77a6e44f3e6a))

- Figure-wide line cap, join and dash length ([#80](https://github.com/BenHuddart/gleplot/pull/80),
  [`99b3234`](https://github.com/BenHuddart/gleplot/commit/99b3234108915d6eff86ebbaf15028e16f98edf1))

- Transparent and grayscale output options on savefig
  ([#79](https://github.com/BenHuddart/gleplot/pull/79),
  [`60f66f4`](https://github.com/BenHuddart/gleplot/commit/60f66f486d41303215746d9dfb081f89fe49a89c))

- Warn when math mode cannot show the axes ([#74](https://github.com/BenHuddart/gleplot/pull/74),
  [`0fcb306`](https://github.com/BenHuddart/gleplot/commit/0fcb306238c9e9bb7bb83c55bec56e294e863f56))

- Warn where savefig's transparent and grayscale cannot act
  ([#79](https://github.com/BenHuddart/gleplot/pull/79),
  [`d5e4ff8`](https://github.com/BenHuddart/gleplot/commit/d5e4ff8a71712b17044e37c13d3a7787402c7dc9))


## v3.17.0 (2026-11-18)

### Features

- Accept numpy numbers and size names in pie, one text per wedge
  ([#56](https://github.com/BenHuddart/gleplot/pull/56),
  [`5d6a075`](https://github.com/BenHuddart/gleplot/commit/5d6a075bec5a767e95e726aa1760448136af6290))

- Pie charts with Axes.pie and glp.pie ([#56](https://github.com/BenHuddart/gleplot/pull/56),
  [`e9aaeb7`](https://github.com/BenHuddart/gleplot/commit/e9aaeb7e5f879f49ae057cb3513da36510d58ec4))


## v3.16.0 (2026-11-18)

### Bug Fixes

- List unknown-cmap alternatives as matplotlib spells them
  ([#55](https://github.com/BenHuddart/gleplot/pull/55),
  [`5a62bbd`](https://github.com/BenHuddart/gleplot/commit/5a62bbdea51137dcbebe8683432c63dfbb4afdf8))

### Features

- ColorBrewer cmaps for imshow and tripcolor ([#55](https://github.com/BenHuddart/gleplot/pull/55),
  [`379a820`](https://github.com/BenHuddart/gleplot/commit/379a8206e830f16f0030bb4bee118f2b483fc928))


## v3.15.0 (2026-11-18)

### Documentation

- Explain the one-colormap limit and why contours have no smoothing
  ([#54](https://github.com/BenHuddart/gleplot/pull/54),
  [`5b010c4`](https://github.com/BenHuddart/gleplot/commit/5b010c454611833f7e341612cb1f418b9b5d2f77))

- Point the migration guide at the heatmap limit instead of restating it
  ([#54](https://github.com/BenHuddart/gleplot/pull/54),
  [`de3c97a`](https://github.com/BenHuddart/gleplot/commit/de3c97ae457e71b2a904bbea6a5ebf81f3a85260))

### Features

- Draw GLE-fitted curves with Axes.fit ([#53](https://github.com/BenHuddart/gleplot/pull/53),
  [`64864e9`](https://github.com/BenHuddart/gleplot/commit/64864e95f873db7f818ac2477b5ef3584268e8a1))

- Name the argument when fit() data is not numbers
  ([#53](https://github.com/BenHuddart/gleplot/pull/53),
  [`2a8387c`](https://github.com/BenHuddart/gleplot/commit/2a8387c22100cbd120d8bbef0904433be60c1a85))


## v3.14.0 (2026-11-18)

### Features

- Draw GLE-sampled function curves with Axes.function
  ([#52](https://github.com/BenHuddart/gleplot/pull/52),
  [`e429caa`](https://github.com/BenHuddart/gleplot/commit/e429caa38a25be427adb9324889a15f7f176c7d0))


## v3.13.0 (2026-11-18)

### Features

- Data-file reading options on line_from_file and errorbar_from_file
  ([#51](https://github.com/BenHuddart/gleplot/pull/51),
  [`08b72c8`](https://github.com/BenHuddart/gleplot/commit/08b72c892a329189fcced23bb0452f42f5fcb2af))


## v3.12.0 (2026-11-18)

### Features

- Plot() mdist, deresolve and per-series clip window
  ([#50](https://github.com/BenHuddart/gleplot/pull/50),
  [`07163ee`](https://github.com/BenHuddart/gleplot/commit/07163ee300301af84941f018207914d890d76eae))


## v3.11.0 (2026-11-18)

### Documentation

- Say that honouring a warned-and-ignored keyword is not breaking
  ([`4341e59`](https://github.com/BenHuddart/gleplot/commit/4341e59eea1951754f591e7e0459d6669c8048a7))

### Features

- Axis-line styling, title fonts and GLE tick placement
  ([`0286c0d`](https://github.com/BenHuddart/gleplot/commit/0286c0d1a704fbd028aae62b6296206750613860))


## v3.10.0 (2026-11-17)

### Features

- Deprecate GLEWriter's keyword-argument series methods (#100 stage 4)
  ([`56a946e`](https://github.com/BenHuddart/gleplot/commit/56a946eae2fb821d2129e2df612e75297ba396d3))


## v3.9.3 (2026-11-17)

### Bug Fixes

- Keep a dataset line's missing colour and width missing on re-save
  ([#134](https://github.com/BenHuddart/gleplot/pull/134),
  [`28fe11a`](https://github.com/BenHuddart/gleplot/commit/28fe11a0be17e8d6dc0336d2285aa0e77803d2a4))

### Documentation

- Add the Opening GLE files guide
  ([`bddb657`](https://github.com/BenHuddart/gleplot/commit/bddb657ce136855c8570ecc7fe4cc09c93d09bcc))

- Generate the gallery from the examples registry
  ([`8caed17`](https://github.com/BenHuddart/gleplot/commit/8caed17f850b9a71e8fb55e11aa28b2f6119feeb))

- Regroup the site navigation into the sections of #104
  ([`0597117`](https://github.com/BenHuddart/gleplot/commit/0597117b5794525206bbf5cca7032ee4729c7620))

- Replace CONFIGURATION_API.md with the generated reference
  ([`2c311b7`](https://github.com/BenHuddart/gleplot/commit/2c311b7146a978b9d7d6b37fc543021ef2c52f6c))

- Split the usage page into user-guide topics
  ([`158342b`](https://github.com/BenHuddart/gleplot/commit/158342bbeac968081a5a372ed0aebaf60d4383dc))

- **contributing**: Build the contributing page from CONTRIBUTING.md
  ([`8d67254`](https://github.com/BenHuddart/gleplot/commit/8d67254215d56aea8d75d597162c3df52c1b11a3))

- **examples**: Keep run_all output apart from run_and_compile's
  ([`3084fe2`](https://github.com/BenHuddart/gleplot/commit/3084fe2aa0a2241fbbaf5fe1ef291466996b9782))

- **examples**: Stop committing generated example output
  ([`97d4ca3`](https://github.com/BenHuddart/gleplot/commit/97d4ca3231c8e428de708117d13127e72dca874c))

- **guides**: Fold the PyPI publishing setup into VERSIONING.md
  ([`8180911`](https://github.com/BenHuddart/gleplot/commit/81809114fbb74b6862e3112190c88572d8b0708d))

- **guides**: Keep the PyPI publishing steps true to release.yml
  ([`27b9c3e`](https://github.com/BenHuddart/gleplot/commit/27b9c3e4a0ccab6c4884ab21d9a9c0364b727a2a))

- **guides**: Link the guides index and sibling guides from the site
  ([`6602888`](https://github.com/BenHuddart/gleplot/commit/6602888da59e86f4a5afcf3648ec7e5eef46b446))

- **guides**: Publish the topic guides on the Sphinx site
  ([`0a2fcd5`](https://github.com/BenHuddart/gleplot/commit/0a2fcd5fc0df4492adae5026107373b96db0e692))

### Refactoring

- Attribute warnings to the caller's line and check for stacklevel
  ([`ec81e84`](https://github.com/BenHuddart/gleplot/commit/ec81e842c89b817f6eee0386fe7e1d2a3690074d))

- Clarify the per-phase write methods in AGENTS.md and the dispatcher docstring
  ([`afd3249`](https://github.com/BenHuddart/gleplot/commit/afd3249b3b5f248fb6b9be110576ef1c1699363f))

- Map dN display attributes to series fields in one place (#100 stage 3)
  ([`a04487b`](https://github.com/BenHuddart/gleplot/commit/a04487b0337c72c31ec459085296923e27c0ce1d))

- Pass bar series to the writer whole (#100 stage 2)
  ([`b74b17e`](https://github.com/BenHuddart/gleplot/commit/b74b17eacfc1bb13e299f620db8c953d082cd1bb))

- Pass contours to the writer whole ([#147](https://github.com/BenHuddart/gleplot/pull/147),
  [`0b49be2`](https://github.com/BenHuddart/gleplot/commit/0b49be25930fd65dd5393cf28ccc96a43aea8667))

- Pass errorbar series to the writer whole (#100 stage 2)
  ([`99a52a9`](https://github.com/BenHuddart/gleplot/commit/99a52a9911016fb76be6ace590b68b497afac6fc))

- Pass file series to the writer whole (#100 stage 2)
  ([`31ff30a`](https://github.com/BenHuddart/gleplot/commit/31ff30ad32eb979d780dcbf2ba690b530ff6ebe2))

- Pass fill series to the writer whole (#100 stage 2)
  ([`d4eef29`](https://github.com/BenHuddart/gleplot/commit/d4eef298ea0a9819502af32ab848e8e67661302b))

- Pass heatmaps to the writer whole ([#147](https://github.com/BenHuddart/gleplot/pull/147),
  [`c5deccb`](https://github.com/BenHuddart/gleplot/commit/c5deccb360f3d4545e58f7f30839314e40b45f51))

- Pass histogram series to the writer whole (#100 stage 2)
  ([`e5b4243`](https://github.com/BenHuddart/gleplot/commit/e5b424325509d5291ff51d10f2998dc4fa0b1f53))

- Pass line series to the writer whole (#100 stage 1)
  ([`f2dcda4`](https://github.com/BenHuddart/gleplot/commit/f2dcda439d17dcc4704d4a506e8bbd44722e3ef9))

- Pass reference lines to the writer whole ([#147](https://github.com/BenHuddart/gleplot/pull/147),
  [`d4e60c7`](https://github.com/BenHuddart/gleplot/commit/d4e60c70d9ba6536e75d6cad45928d123ec64737))

- Pass scatter series to the writer whole (#100 stage 2)
  ([`dbd98cb`](https://github.com/BenHuddart/gleplot/commit/dbd98cb8c0eca75740880cad75b9cbb3f748dbc0))

- Pass spans to the writer whole ([#147](https://github.com/BenHuddart/gleplot/pull/147),
  [`17c5b76`](https://github.com/BenHuddart/gleplot/commit/17c5b768f1a45006f8008816da53b3aca517a972))

- Pass text annotations to the writer whole ([#147](https://github.com/BenHuddart/gleplot/pull/147),
  [`2a04db5`](https://github.com/BenHuddart/gleplot/commit/2a04db5fee08497a7b453c5fc42bbc93095238d1))

- Route every library warning through warn_external
  ([`1923c6c`](https://github.com/BenHuddart/gleplot/commit/1923c6ce7650eeead087b060b10b99b58287ece2))

- Say nbars can exceed 1 for a grouped bar in the G16 note
  ([`17bb811`](https://github.com/BenHuddart/gleplot/commit/17bb81194804f90865ebbf9a5218a1fced9ea77d))

- Split _Recognizer._parse_graph_block into named steps
  ([#109](https://github.com/BenHuddart/gleplot/pull/109),
  [`c6bfc76`](https://github.com/BenHuddart/gleplot/commit/c6bfc7693690e6990a072806b3b1e6d60b4cffb5))

- Split _Recognizer.run into its phases ([#109](https://github.com/BenHuddart/gleplot/pull/109),
  [`c38c674`](https://github.com/BenHuddart/gleplot/commit/c38c674ddd6e29b1ee3be274eb80978b272190f1))

- Split Figure._write_axes_content into per-phase methods
  ([`06616eb`](https://github.com/BenHuddart/gleplot/commit/06616eb05c138d547bc74beffb05f263fe5caf8b))

- Split GLEWriter.add_axes into per-axis steps
  ([#109](https://github.com/BenHuddart/gleplot/pull/109),
  [`52d7bd8`](https://github.com/BenHuddart/gleplot/commit/52d7bd82bafd3b9f913ad5adf1de38a1862d1118))

- Tidy the graph-block pass state ([#109](https://github.com/BenHuddart/gleplot/pull/109),
  [`30d9824`](https://github.com/BenHuddart/gleplot/commit/30d9824c7c2920cc2e44b9e3f3c769c0a0aea80c))

- **examples**: Leave compiling to the runner
  ([`f4cf69d`](https://github.com/BenHuddart/gleplot/commit/f4cf69dc66eacaaed2c6d16c848c88ceb4547807))

- **examples**: One registry and one runner for the examples
  ([`82c4e59`](https://github.com/BenHuddart/gleplot/commit/82c4e594ba82f6b2f1c2bb2fed5fd997f999b1ab))

### Testing

- Add a golden builder for the bar fields no builder set
  ([`df5b7c7`](https://github.com/BenHuddart/gleplot/commit/df5b7c766ce35dc34dfc3b4ffd92bdc98329f4a3))

- Add a golden builder for the contour fields no builder set
  ([`76202d1`](https://github.com/BenHuddart/gleplot/commit/76202d1d90987c979a04c60fed0cfb8e6db74095))

- Add a golden builder for the errorbar fields no builder set
  ([`35f5f58`](https://github.com/BenHuddart/gleplot/commit/35f5f58d71b3d7abadd2e55405dba2d5ba860df6))

- Add a golden builder for the file-series fields no builder set
  ([`c95ee4f`](https://github.com/BenHuddart/gleplot/commit/c95ee4f1e8111befd0093c075b7e63ed705a8a97))

- Add a golden builder for the fill fields no builder set
  ([`af79979`](https://github.com/BenHuddart/gleplot/commit/af79979b73bf25dd6a146455307e700549ae1b14))

- Add a golden builder for the heatmap fields no builder set
  ([`c961055`](https://github.com/BenHuddart/gleplot/commit/c9610555d91a50028a1f2e9e15e30e0619291e4c))

- Add a golden builder for the histogram fields no builder set
  ([`f704b9f`](https://github.com/BenHuddart/gleplot/commit/f704b9fe5928f9f61295f1a7ba7abdfbbb7839f6))

- Add a golden builder for the line fields no builder set
  ([`3cb454e`](https://github.com/BenHuddart/gleplot/commit/3cb454e856efb42d76316278d68d46abf0f21a7b))

- Add a golden builder for the scatter fields no builder set
  ([`6a9297d`](https://github.com/BenHuddart/gleplot/commit/6a9297d25114a71a090445d5d859bc5e379767c3))

- Check warn_explicit too and keep attribution-test cleanup in finally
  ([`77f4afb`](https://github.com/BenHuddart/gleplot/commit/77f4afb091d3d61b7c929bac59da62e54f54b96e))

- Convert the remaining unittest modules to pytest and remove tests/_tempdir.py
  ([`c31f43d`](https://github.com/BenHuddart/gleplot/commit/c31f43dfa9ea7f6d4e12cb9603f0d659d0d313de))

- Cover an unloadable error-bar dataset before folding the dN field mapping
  ([`1dbe6e3`](https://github.com/BenHuddart/gleplot/commit/1dbe6e35049756f9550ceb2cef92ad9ff915ea11))

- Cover the page-level trailer branches before splitting _Recognizer.run
  ([`3208a7a`](https://github.com/BenHuddart/gleplot/commit/3208a7a30c24968681dffad673fdd34189882678))

- Cover the y-side tick options before splitting GLEWriter.add_axes
  ([`c3e5931`](https://github.com/BenHuddart/gleplot/commit/c3e59318bdfc2b73113106f0ad1c0142cfce50b7))

- Hold third-party imports to the declared runtime dependencies
  ([`230073d`](https://github.com/BenHuddart/gleplot/commit/230073db0bd9d0077963a0bc4372cbfbd6a81ee5))

- Keep an unpaired histogram let as raw GLE with a note
  ([`f3e3c6c`](https://github.com/BenHuddart/gleplot/commit/f3e3c6cc4ddfc77d0741c36052e501a6754a0490))

- Keep the first-UserWarning check and use pathlib for tmp_path joins
  ([`d370292`](https://github.com/BenHuddart/gleplot/commit/d37029256dfa88031ea91238be8d88f8a33f0c88))

- Move the unpaired histogram let test to the parser layer
  ([`47b78d6`](https://github.com/BenHuddart/gleplot/commit/47b78d60a2b338ee092e522ef02c04322c16d721))

- Pin add_plot_line's keyword mapping and repoint stale comments
  ([`dd55e04`](https://github.com/BenHuddart/gleplot/commit/dd55e04833c8a878c8fe250eee5da5d7c7f0d24a))

- Round-trip a styled, fractional draw-form reference line
  ([`8284cad`](https://github.com/BenHuddart/gleplot/commit/8284cada1e6b1b4b3b3a7a8e3786b4465d7b9809))

- Round-trip a styled, fractional draw-form span
  ([`7c270ed`](https://github.com/BenHuddart/gleplot/commit/7c270ed932c71863aaeeccf54a0935b4af950ee1))

- Share one import walker and parse dependency specs robustly
  ([`36d9598`](https://github.com/BenHuddart/gleplot/commit/36d9598601964f10829b95614739cb64c2c3f5d7))

- Strip the directory from data_error with Path, not a slash regex
  ([`e269e10`](https://github.com/BenHuddart/gleplot/commit/e269e10f069febd7a9071700a2b866e98048acc1))


## v3.9.2 (2026-11-17)

### Bug Fixes

- Stop printing from library code; make show() view the figure
  ([`34e04c0`](https://github.com/BenHuddart/gleplot/commit/34e04c006af2d008860c474d77bcafc0efadf259))

### Continuous Integration

- Clear the mypy errors and make the type check gate the build
  ([`2c26a2f`](https://github.com/BenHuddart/gleplot/commit/2c26a2f9bcaf56bdf7ad8a8a55ee6122cd3805d7))

- Run the examples and a strict Sphinx build on pull requests
  ([`c65d78e`](https://github.com/BenHuddart/gleplot/commit/c65d78eaea30f4b18652097a31f63f49d1ca77e2))

### Documentation

- Link each known-debt entry to its issue
  ([`2f6ad2f`](https://github.com/BenHuddart/gleplot/commit/2f6ad2f0833c80938e08121e7162ef6729012011))

- State the agent contract as the target form and list known debt
  ([`bddd2ce`](https://github.com/BenHuddart/gleplot/commit/bddd2cea9178fee8c20d06d3b528a3b007adef80))

### Refactoring

- Make module-level imports acyclic and test the layering
  ([`06cf064`](https://github.com/BenHuddart/gleplot/commit/06cf064dfcb5224927a56748c6f3149078dd0a7a))

### Testing

- Count drawn segments instead of timing the decimated compile
  ([`4e6a277`](https://github.com/BenHuddart/gleplot/commit/4e6a277af30d6c92f74839fb6cb7c14fa2650421))


## v3.9.1 (2026-11-16)

### Bug Fixes

- Discover series fields on Python 3.14
  ([`b9b518b`](https://github.com/BenHuddart/gleplot/commit/b9b518b886c99d54a27413d86f60a8d2c39bd9eb))

### Build System

- Raise the Python floor to 3.9 and configure the lint tools
  ([`a5e5779`](https://github.com/BenHuddart/gleplot/commit/a5e5779c183c4b5de11661498a3e37ba854ff7b0))

### Code Style

- Format the tree with black and isort
  ([`c1f6006`](https://github.com/BenHuddart/gleplot/commit/c1f60062b841d63b4fd47dc9eec3a802fdfcab8d))

### Continuous Integration

- Bound the parallel GLE build
  ([`c990314`](https://github.com/BenHuddart/gleplot/commit/c990314bb397fc2839fd695acb0cfaf49c32d36e))

- Cache the GLE build and move the version spread to the no-GLE job
  ([`b99ca06`](https://github.com/BenHuddart/gleplot/commit/b99ca0626d044ab46bb83476794c6a2315bece68))

- Run the no-GLE job on ubuntu-24.04
  ([`7c0f7f7`](https://github.com/BenHuddart/gleplot/commit/7c0f7f74a4f2a9240708e5db2cacafa371bb0a9f))

### Documentation

- Prune stale pages and complete the API reference
  ([`aee7dd3`](https://github.com/BenHuddart/gleplot/commit/aee7dd3eee8aa5378c13e67314cbd898aea373f9))

### Testing

- Skip GLE-dependent tests through the gle marker and lint in CI
  ([`10ba438`](https://github.com/BenHuddart/gleplot/commit/10ba4387844788b89c8aa3e7b6559ad9fe9b9992))


## v3.9.0 (2026-11-16)

### Features

- Add Axes.annotate with data-coordinate arrows
  ([`8b9e202`](https://github.com/BenHuddart/gleplot/commit/8b9e2024a2208e4eb9c66ec001ce60e6c73396b3))


## v3.8.0 (2026-11-15)

### Features

- Add a secondary x axis as a data scale
  ([`001232a`](https://github.com/BenHuddart/gleplot/commit/001232a7ad8458a5b584768cef4d5f8b449aa007))


## v3.7.0 (2026-11-15)

### Features

- Draw error bars on bar charts
  ([`e7737b4`](https://github.com/BenHuddart/gleplot/commit/e7737b43346c7f34c93d79d60fb0f4cedd47513b))


## v3.6.0 (2026-11-14)

### Features

- Model bar colors, horizontal bars, groups, and stacks
  ([`0603d41`](https://github.com/BenHuddart/gleplot/commit/0603d41a4ed386ac12e040c72a91b91a44ab19d8))


## v3.5.0 (2026-11-14)

### Features

- Fill to an axis, clip bands, and fill polygons
  ([`8420553`](https://github.com/BenHuddart/gleplot/commit/8420553df25c8b677f0f9770c2bf50e09a71961f))


## v3.4.0 (2026-11-14)

### Features

- Bin samples with Axes.hist
  ([`93f1970`](https://github.com/BenHuddart/gleplot/commit/93f19709025710304aec46c0576cbcca963b7bad))


## v3.3.0 (2026-11-14)

### Features

- Emit step, stem, and histogram outlines as GLE line modes
  ([`45f91f8`](https://github.com/BenHuddart/gleplot/commit/45f91f801a0962bea3e017f7486bbd926b4ed3da))


## v3.2.0 (2026-11-14)

### Features

- Draw bar and fill labels in the legend
  ([`022ec15`](https://github.com/BenHuddart/gleplot/commit/022ec15729b14184470fdf21291c4bb44ab8d61e))

### Testing

- Expect a legend swatch on a labelled span
  ([`827c996`](https://github.com/BenHuddart/gleplot/commit/827c996c0595d72ba1d64f66cc10c99ae4ac3118))


## v3.1.0 (2026-11-14)

### Features

- Emit text vertical alignment, rotation, and backgrounds
  ([`c95857a`](https://github.com/BenHuddart/gleplot/commit/c95857a3b269539fe5e24912923365cc6563d914))

### Testing

- Refresh text annotation emission digests
  ([`cbb045c`](https://github.com/BenHuddart/gleplot/commit/cbb045ca0a0d531debbcd92777e145b1361b85f9))


## v3.0.0 (2026-11-14)

### Continuous Integration

- Simplify release to PSR v10 and gate PyPI
  ([`8359a69`](https://github.com/BenHuddart/gleplot/commit/8359a6977f885c43f9e5a6f6c3d12645d73663b0))

### Features

- Remove calibration v2
  ([`07c3d4e`](https://github.com/BenHuddart/gleplot/commit/07c3d4eba337c72b14d7f298a938793369b65fbb))

- Remove the desktop GUI
  ([`32eebc5`](https://github.com/BenHuddart/gleplot/commit/32eebc57687e5bc0ec44929d1f0ee5990827acea))


<!-- Hand-written notes for work that does not yet have a generated release
     section. python-semantic-release inserts new releases above this comment.
     Delete this section once a generated release covers the same changes. -->

## Unreleased

### Features

- `ax.legend()` honours `fontsize` (GLE `key ... hei`, points converted with
  the same pt→cm rule as `set hei`, including matplotlib's relative names) and
  `frameon` (`key ... nobox`); all eleven matplotlib `loc` strings now reach
  GLE's nine key anchors instead of five of them collapsing onto top right
- Every other matplotlib `legend()` keyword — and an unrecognized `loc`, and
  an explicit handles/labels sequence — warns instead of being silently
  dropped
- `ax.contour(X, Y, Z)` accepts matplotlib's 2-D `np.meshgrid` coordinate
  arrays; irregular grids, transposed (`indexing='ij'`) grids and shape
  mismatches each raise their own message

### Behaviour changes

- **Plain display strings now render literally.** GLE's text engine reads `_`
  and `^` as sub/superscripts and swallows braces, so `'lambda_tail'` used to
  render as "lambda" with a subscripted "tail" and `'{a, b}'` lost its braces.
  gleplot now follows matplotlib's contract — literal by default, math opt-in
  via `$...$` — and escapes `_`, `^`, `{` and `}` in every non-math segment of
  every display string (axis labels, titles, legend keys, annotations, tick
  labels).

  Still treated as GLE markup, so existing figures that use it are unaffected:
  a **backslash** (`r'\chi{} (emu/mol)'`, `'{\bf bold}'`) and a **braced**
  script (`'T_{N}'`, `'mol^{-1}'`). Only a *bare* `_`/`^` changed meaning. If
  you relied on `'T_N'` subscripting, write `'T_{N}'` or `r'$T_N$'`.

### Fixes

- `gleplot.calibration` hardens `glestudio-cal`/`glestudio-box`/`glestudio-tw`
  markers against spoofing: an optional per-invocation `nonce` on
  `instrument_script`/`inject_text_metrics`/`build_text_metric_script`
  (`new_calibration_nonce()` mints one) embeds `marker:<nonce>` in every
  printed record, and `parse_calibration_records(..., expected_nonce=...)`
  rejects any record whose marker lacks or mismatches it as a new `"spoofed"`
  `CalibrationWarning`, instead of letting it race the genuine record for the
  first-parsed slot. Fixes a hole where a `print "glestudio-cal ..."`
  smuggled into a document as passthrough text (axes ids travel in
  GLEstudio's `project.json` plaintext) could poison the data↔cm map before
  the real record — printed after the actual graph block — ever arrived.
  Opt-in: omitting `nonce`/`expected_nonce` reproduces prior behaviour
  exactly.

## v1.9.0 (2026-07-31)

### Features

- `Figure.add_broken_xaxes` — split/broken x-axis figures, rendered as
  independent GLE subplot segments with a shared y-axis and configurable
  divider style (double-slash, single rule, or none)
- `axhline`/`axvline`/`axhspan`/`axvspan` as first-class `Axes` methods,
  matplotlib-compatible reference lines and shaded spans
- `Axes.set_xticks`/`set_yticks` accept `dticks`/`dsubticks` for explicit
  major/minor tick spacing
- `height_ratios`/`width_ratios` on `Figure`/`glp.figure`/`glp.subplots` for
  matplotlib-`gridspec`-style uneven subplot grids
- Open (outline) and white-filled marker variants, selected via `fillstyle`
  or `markerfacecolor`/`mfc` on `plot`, `scatter`, and `errorbar`
- `scatter` accepts `markersize` (matplotlib `Line2D` diameter convention)
  alongside its existing `s` (area) convention; passing both prefers
  `markersize`
- Every matplotlib string marker code is now mapped to a GLE glyph

### Fixes

- Colours are emitted as exact `rgb255(...)` values instead of being snapped
  onto the nearest of ~8 named GLE colours
- Line series are drawn as the data itself rather than a spline through it
  unless smoothing is explicitly requested (`GLEGraphConfig.smooth_curves`
  now defaults to `False`)
- Line styles use the GLE line-style numbers that actually render as their
  names say (dashed, dotted, and dash-dot no longer render as each other)
- Error bars and their caps consistently take the series colour, including
  bars-only error series
- `Figure(data_prefix=...)` is validated instead of silently producing GLE
  scripts that fail to parse

## v1.0.1 (2026-03-03)

### Improvements

- Gallery updated to use example outputs instead of test suite outputs
- All gallery code snippets now match the actual example source files
- New examples added: conditional `fill_between` (with `where=`), combined X+Y error bars,
  side-by-side subplots (1×2), stacked subplots (2×1), 2×2 mixed-type subplot grid, 1×3 comparison
- Documentation homepage now includes prominent links to the GitHub repository
- GitHub Pages deployment workflow fixed (`fetch-tags: true`)

## v0.0.1 (2026-03-01)

### Features

- Initial release of gleplot
- Matplotlib-compatible API for creating GLE plots
- Support for line plots, scatter plots, bar charts, and fill_between
- Full axis customization (labels, limits, scales, grid)
- Color and marker mappings compatible with matplotlib
- Direct compilation to PDF, PNG, and EPS via GLE
- Export to GLE scripts for manual editing
- Comprehensive test suite with 34 tests
- Sphinx documentation with GitHub Actions publishing
- Examples gallery demonstrating various plot types
