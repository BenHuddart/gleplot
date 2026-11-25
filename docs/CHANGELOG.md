# CHANGELOG

<!-- version list -->

## v6.1.0 (2026-11-25)

### Bug Fixes

- Address review of opaque_backdrop (strings, comments, legend, hex alpha)
  ([`d850f74`](https://github.com/BenHuddart/gleplot/commit/d850f74988d8373b0c911c8be5ce98091364486a))

### Documentation

- Describe PyPI publishing as live now that 6.0.0 is on PyPI
  ([`2dd62ec`](https://github.com/BenHuddart/gleplot/commit/2dd62ec376777f01a6569ebd1ccd9681f67efefb))

### Features

- Add GLEStyleConfig(opaque_backdrop=...) for native no-alpha export
  ([`0bf15e1`](https://github.com/BenHuddart/gleplot/commit/0bf15e127ce31e1173d335d286bc8ed898ac15de))


## v6.0.0 (2026-11-22)

### Bug Fixes

- A NaN bar height is written missing, so the bar is left out
  ([`7b83836`](https://github.com/BenHuddart/gleplot/commit/7b8383689d62bdeae13fac596be0c55daee0f5d6))

- A span keeps a fill whose second curve alone is shifted
  ([`1de367c`](https://github.com/BenHuddart/gleplot/commit/1de367cfddf14a9e7a15f2da0f949fdb44330e18))

- Accept ds='default' on a polar axes as drawstyle='default' is
  ([`a3e3335`](https://github.com/BenHuddart/gleplot/commit/a3e333548f64d1729322a93f41c5a14ab103131c))

- Accept matplotlib's linewidths=None default in contour and tricontour
  ([`6ff0442`](https://github.com/BenHuddart/gleplot/commit/6ff044225dd1a257ece8d3a4d1cbf1ef2da84da4))

- Accept matplotlib's twiny() signature
  ([`e825678`](https://github.com/BenHuddart/gleplot/commit/e8256784069f346651ff70cc0eddf55484b46c63))

- Add_subplot rejects an index off the grid at the call
  ([`0942333`](https://github.com/BenHuddart/gleplot/commit/0942333d682ed0464213d6c871d35fe1cb954fa8))

- Address review of colorbars drawn by color.gle
  ([`2db3bc4`](https://github.com/BenHuddart/gleplot/commit/2db3bc423c3d31d1103d7ee8dd24d4d85e6349ae))

- Address review of rugs drawn by rugs.gle
  ([`ffbad05`](https://github.com/BenHuddart/gleplot/commit/ffbad058e0c8684098493041d5ac8d6fd5d693aa))

- Address review of the after-graph guide form
  ([`521aa3e`](https://github.com/BenHuddart/gleplot/commit/521aa3ea34931ab42326c18653399b06516123e0))

- Autoscale the primary y axis from the primary series only
  ([#142](https://github.com/BenHuddart/gleplot/pull/142),
  [`1fe31cf`](https://github.com/BenHuddart/gleplot/commit/1fe31cf3836281c6f94b7b007a6762e2d2fb587d))

- Axhline/axvline(linewidth=None) draw the default width
  ([`d6644f4`](https://github.com/BenHuddart/gleplot/commit/d6644f4bf863b68c5bfac4671ed847276415a2c0))

- Axis() checks every limit before setting any; get_xlim/get_ylim check axis
  ([`e13d662`](https://github.com/BenHuddart/gleplot/commit/e13d6622a73743d9f01421959860b37f818d287e))

- Bind raw GLE lines to the datasets they read when a loaded figure is saved
  ([#310](https://github.com/BenHuddart/gleplot/pull/310),
  [`030aea7`](https://github.com/BenHuddart/gleplot/commit/030aea7d1ed34aa24776dbf42f4e11ad08e5eee8))

- Bind raw reads of an error-bar file series apart from derived sources
  ([#453](https://github.com/BenHuddart/gleplot/pull/453),
  [`0952ec8`](https://github.com/BenHuddart/gleplot/commit/0952ec88a4c07aaa6fc7c7958d330338a886f792))

- Bind raw reads of bar, fill, histogram and error-bar datasets
  ([`c1a1b88`](https://github.com/BenHuddart/gleplot/commit/c1a1b883d87ba8965c8707914165e99dc6b5fc29))

- Bind raw reads of error datasets; take a series' offset from it
  ([`782904e`](https://github.com/BenHuddart/gleplot/commit/782904ee5738641897c39c2af560e383d8a0254b))

- Break a plotted line at NaN, as matplotlib does
  ([`a035489`](https://github.com/BenHuddart/gleplot/commit/a03548970017620914d1ba25406f814d4142371a))

- Break a provider-backed line at NaN, as plot does
  ([`3d6d6f2`](https://github.com/BenHuddart/gleplot/commit/3d6d6f21f5ce493ab9e1620ab239d252e6173613))

- Break a table-backed gap series at its NaN rows
  ([`33c1f56`](https://github.com/BenHuddart/gleplot/commit/33c1f56574e6a1244ebc204b756b47ceff57010d))

- Break at inf too, warn when a gapped line is not smoothed or thinned
  ([`7cc7842`](https://github.com/BenHuddart/gleplot/commit/7cc7842e534d52a81d91ab0309681cce425e9c9c))

- Bring the remaining calls onto the shared unknown-keyword warning
  ([`5f32ef0`](https://github.com/BenHuddart/gleplot/commit/5f32ef01f14c94c5d441f12500a60f131be095c7))

- Check a guide's marker extent against its rows on load
  ([`bb071af`](https://github.com/BenHuddart/gleplot/commit/bb071afd997126146e2d2118b96fffa33327d848))

- Check axhspan/axvspan edges and broken-y guides for finite positions too
  ([`d32a59b`](https://github.com/BenHuddart/gleplot/commit/d32a59bf03c285a6ef2fa7c57e848fb66aca4b80))

- Check linewidth on hist step, function/fit curves and vlines too
  ([`6b49993`](https://github.com/BenHuddart/gleplot/commit/6b499932ad8987a930a24f2f294f26634a5ea15f))

- Compare a guide's ends as re-saving would write them
  ([`42284a3`](https://github.com/BenHuddart/gleplot/commit/42284a328086ea5c530a89f9d2356277b4ac045f))

- Compile SVG with -cairo so text in the default font is drawn
  ([`ba579bd`](https://github.com/BenHuddart/gleplot/commit/ba579bd2c34a7a1128706a8e38f3cfe0f76c056b))

- Decide an offset let's fate once every data statement is read
  ([#381](https://github.com/BenHuddart/gleplot/pull/381),
  [`db86071`](https://github.com/BenHuddart/gleplot/commit/db8607162bb419b10cee4dcc12a69b9bef561166))

- Decide raw error bars once, from errors a let computes
  ([`b0a6974`](https://github.com/BenHuddart/gleplot/commit/b0a6974e05a2bf256b8ee5e1d20a231cc36ca907))

- Decide which imported files raw GLE shares once the figure is read
  ([`2afe8ab`](https://github.com/BenHuddart/gleplot/commit/2afe8abc22fe0fd0ade288c39459afb2d76014ce))

- Decode GLE's output as UTF-8, including GLECompiler.info()
  ([`fc9b111`](https://github.com/BenHuddart/gleplot/commit/fc9b11154433ae1dea6ae4caee2cfc855d02fe39))

- Describe and test the table-backed gap columns
  ([`b125404`](https://github.com/BenHuddart/gleplot/commit/b1254048fe94ac1f0956dfb0591e391848e11166))

- Disown an owned data file only when saving would change it
  ([`13758be`](https://github.com/BenHuddart/gleplot/commit/13758be91e64e81f455b58e908170b7846e7318e))

- Document where None is the default line style and drop dead None tests
  ([`0aad075`](https://github.com/BenHuddart/gleplot/commit/0aad0751c9a0def7f459c1c3c359e07886fa2132))

- Draw 'none' and zero-alpha faces as CLEAR, and warn on an empty bar swatch
  ([`beb3126`](https://github.com/BenHuddart/gleplot/commit/beb3126f5099d48f1c1606f4cfb51f19838d9985))

- Draw a contourf's colorbar as its bands, ticked at the levels
  ([#258](https://github.com/BenHuddart/gleplot/pull/258),
  [`238d6de`](https://github.com/BenHuddart/gleplot/commit/238d6de6f93c9c1698f3c89ffa9a21ef69b5d2b7))

- Draw a step histogram in its edgecolor, as matplotlib does
  ([`d65eff7`](https://github.com/BenHuddart/gleplot/commit/d65eff73cbd0dfcbd0e78524dcb490d1b5dc7a6c))

- Draw an inverted image's colorbar in the reversed palette
  ([#231](https://github.com/BenHuddart/gleplot/pull/231),
  [`ef44a2b`](https://github.com/BenHuddart/gleplot/commit/ef44a2ba7d8b8fe32651fef75a4274fcb39bdbfd))

- Draw linestyle=None as matplotlib's default solid line
  ([`18e5669`](https://github.com/BenHuddart/gleplot/commit/18e5669d6f24db82c77aa9ed6b6f7113926df81a))

- Draw no bar edge from linewidth or linestyle without edgecolor
  ([`9bdaa14`](https://github.com/BenHuddart/gleplot/commit/9bdaa14c2625b7f29267d1d47dd77f2ba9716db7))

- Draw no line for a line_from_file reference with linestyle='none'
  ([`af29c97`](https://github.com/BenHuddart/gleplot/commit/af29c976d14f5cf63864049122cff679caed0a4b))

- Draw no line for linewidth=0, as matplotlib's lw=0 draws no stroke
  ([`03084ec`](https://github.com/BenHuddart/gleplot/commit/03084ec5475251b50f6b4fb4ca94e5bcb544efba))

- Draw no ticks and no labels for set_xticks([]) / set_yticks([])
  ([`bf53ff4`](https://github.com/BenHuddart/gleplot/commit/bf53ff40526ff0366bc456ff43e230bfe523b0a8))

- Give a collapsed range a margin when no dataset can widen it
  ([`3bdfce7`](https://github.com/BenHuddart/gleplot/commit/3bdfce732ddac141f13ecc2c1e883b40c1f4eb12))

- Give the EPS-image Cairo warning the same specific reason
  ([`fbcc1a5`](https://github.com/BenHuddart/gleplot/commit/fbcc1a56fdfbe6dd4597ae0a6f0459e3f7523f6e))

- Hold bar, histogram, fit and after-graph guide numbers to their axis
  ([`c7d6b85`](https://github.com/BenHuddart/gleplot/commit/c7d6b85e48e01decf912646621f52b029a2e6f5d))

- Hold lone data-unit coordinates to their axis's precision
  ([`e2d85a4`](https://github.com/BenHuddart/gleplot/commit/e2d85a49eab7b4423a4c6a50e5343133a560e771))

- Hold the data a redefined let reads with it
  ([#379](https://github.com/BenHuddart/gleplot/pull/379),
  [`cfcfa89`](https://github.com/BenHuddart/gleplot/commit/cfcfa899dc91fd04e4e17e5161b380e6e9dd810b))

- Ignore NaN and infinite values when autoscaling axis limits
  ([`faaf928`](https://github.com/BenHuddart/gleplot/commit/faaf92857a5de9b3a7d6089f1b371e59816b126a))

- Ignore non-finite guide coordinates when autoscaling
  ([`48a331c`](https://github.com/BenHuddart/gleplot/commit/48a331c7de846602f908fd8eaa63a3103a1f7f91))

- Judge a log-axis scatter drop on y plus its offset
  ([`ab82358`](https://github.com/BenHuddart/gleplot/commit/ab823585b5762d4d80e4286b6b4532eced8227ce))

- Judge per axis whether GLE can widen a collapsed range
  ([`bc6bd3e`](https://github.com/BenHuddart/gleplot/commit/bc6bd3e093c31b0232555cef65ebf199bae14111))

- Keep a (scalar, per-point) errorbar pair and short error messages
  ([`c2de377`](https://github.com/BenHuddart/gleplot/commit/c2de377beb30c0ed10a6276a26b14b9f8abdfa1e))

- Keep a 0 or 1 pt width read from a .gle file as written
  ([#172](https://github.com/BenHuddart/gleplot/pull/172),
  [`205a486`](https://github.com/BenHuddart/gleplot/commit/205a486b61f12087abde39c9bda33408c90a398a))

- Keep a band narrower than float noise where it is
  ([`92e60d8`](https://github.com/BenHuddart/gleplot/commit/92e60d8af9dae75763fe245e84451ea3df56e83f))

- Keep a begin key with a hand-edited swatch as written
  ([`15bf836`](https://github.com/BenHuddart/gleplot/commit/15bf836833c4873492ec31148946add7f9e80472))

- Keep a colorbar in another palette than its heatmap's as raw GLE
  ([`cec8ce6`](https://github.com/BenHuddart/gleplot/commit/cec8ce60af7472120613aae80b4e5016994a67de))

- Keep a contour block whose levels open_gle cannot read as written
  ([#176](https://github.com/BenHuddart/gleplot/pull/176),
  [`62e9fed`](https://github.com/BenHuddart/gleplot/commit/62e9fed0aeb2e9837ae15436699ff7bf55a231cf))

- Keep a data statement gleplot cannot write back as raw GLE, with its readers
  ([#322](https://github.com/BenHuddart/gleplot/pull/322),
  [`e7fc3dc`](https://github.com/BenHuddart/gleplot/commit/e7fc3dc262e63645f78cb6a09e471c9298b93a26))

- Keep a fill raw when its two curves have different offsets
  ([`b0c6bf3`](https://github.com/BenHuddart/gleplot/commit/b0c6bf327b125f9fbbf6e7767f18a325922db964))

- Keep a fitz block open_gle cannot read whole as written
  ([#380](https://github.com/BenHuddart/gleplot/pull/380),
  [`fb5fc28`](https://github.com/BenHuddart/gleplot/commit/fb5fc28648903f3d7da7ee4e1c1137f3a94ea9ab))

- Keep a gleplot data file that raw GLE also reads from being rewritten
  ([`788490e`](https://github.com/BenHuddart/gleplot/commit/788490e9a702efe4f26bb935320b24b4d77364ad))

- Keep a hist face colour's alpha off its edge; stroke 'none' in the fill
  ([`4d32546`](https://github.com/BenHuddart/gleplot/commit/4d32546530788809972996dde5ef67c514276f56))

- Keep a histogram let on a user's own data file as raw GLE
  ([#174](https://github.com/BenHuddart/gleplot/pull/174),
  [`febaeff`](https://github.com/BenHuddart/gleplot/commit/febaeff2b16dc8541d085cd48e3b9f4a8a3a525e))

- Keep a let redefined by a later let as raw GLE
  ([#379](https://github.com/BenHuddart/gleplot/pull/379),
  [`6946b0b`](https://github.com/BenHuddart/gleplot/commit/6946b0b9a0f198dbcbf42ed731b0252886e81234))

- Keep a loaded contour line's unset colour and width unset
  ([`1248a86`](https://github.com/BenHuddart/gleplot/commit/1248a862053d3d98bcd73377995d4095f11e8fb4))

- Keep a loaded file's layout around its raw GLE on re-save
  ([`387a05d`](https://github.com/BenHuddart/gleplot/commit/387a05d469b843f1f233ae600fff2cd9010f6f57))

- Keep a log axis' minor ticks under set_xticks([]), as matplotlib does
  ([`9152367`](https://github.com/BenHuddart/gleplot/commit/91523678da16673c15198f970af94cdce0242a74))

- Keep a raw bar's or hist let's data beside a modelled sibling
  ([`aa212ef`](https://github.com/BenHuddart/gleplot/commit/aa212ef7af3d91e09c959d05784697d18025b1e2))

- Keep a raw histogram's source defined and ignore strings when counting readers
  ([#174](https://github.com/BenHuddart/gleplot/pull/174),
  [`9347245`](https://github.com/BenHuddart/gleplot/commit/9347245b10e9b14873abef1b974768788b9496c7))

- Keep a recovered 0 or 1 pt contour width as written
  ([#172](https://github.com/BenHuddart/gleplot/pull/172),
  [`135c549`](https://github.com/BenHuddart/gleplot/commit/135c54972181c94f904978b2098ad2fdf2f50053))

- Keep a shared data file whole when re-saving a loaded figure
  ([`7168ecd`](https://github.com/BenHuddart/gleplot/commit/7168ecdfd4034758f0e2a0872ca9975a5e0f14b9))

- Keep a stack missing on one side only as raw GLE
  ([`ab66af9`](https://github.com/BenHuddart/gleplot/commit/ab66af9ddfa0d7053eca73db53db657bf030a1f1))

- Keep a twin scale's ticks when the primary axis has none
  ([`c23f921`](https://github.com/BenHuddart/gleplot/commit/c23f9213d5035e438d4fc8827fc16f784d7b3a5d))

- Keep a vertical colorbar's negative sep on reload
  ([`7d48abc`](https://github.com/BenHuddart/gleplot/commit/7d48abc01e7fe37a677c3f9f9fdd3ad7e57a5553))

- Keep an axis range of float noise apart when it is written
  ([`ecd491b`](https://github.com/BenHuddart/gleplot/commit/ecd491bf990238827beeef30851534cc4540ab8d))

- Keep an edited contourf band sub and its colormap as raw GLE
  ([`91fc2b7`](https://github.com/BenHuddart/gleplot/commit/91fc2b71e9dc25b8b66eb526281227ae83e04f27))

- Keep an error bar raw when its errors are read through a let
  ([`ef7b78c`](https://github.com/BenHuddart/gleplot/commit/ef7b78cd1ca49dbf9aadc2413cf7d25160b9e82d))

- Keep an error bar raw when its errors come from another file
  ([`9c27b05`](https://github.com/BenHuddart/gleplot/commit/9c27b0511937ce8ec65346f3a46bc6b489b23707))

- Keep an error-bar line on a user's file raw when a reference loses part of it
  ([#188](https://github.com/BenHuddart/gleplot/pull/188),
  [`5e85306`](https://github.com/BenHuddart/gleplot/commit/5e85306d5459be5a5ab5f27f278c2526f8eca981))

- Keep an inverted heatmap's bar on load beside same-palette scatters
  ([#231](https://github.com/BenHuddart/gleplot/pull/231),
  [`5393c13`](https://github.com/BenHuddart/gleplot/commit/5393c13038aee8a6ca080f3094cc75867a0f7299))

- Keep an offset let on a sidecar that does not load (#381, #453)
  ([`2e11211`](https://github.com/BenHuddart/gleplot/commit/2e1121164bdf7eeaf668db9daeb320f52d13ce1d))

- Keep an offset let on a user's file reading the data it shifts
  ([#453](https://github.com/BenHuddart/gleplot/pull/453),
  [`36b03bf`](https://github.com/BenHuddart/gleplot/commit/36b03bff3b747fd8ae307fc8f929ab8df037b0de))

- Keep an offset let or a two-file fill on a user's file raw
  ([`ed0df7d`](https://github.com/BenHuddart/gleplot/commit/ed0df7dea1a2f099470991e6645d60f96ff3a420))

- Keep each fill curve's own offset instead of keeping the fill raw
  ([`b817b76`](https://github.com/BenHuddart/gleplot/commit/b817b7611e52673e315adcee51ddf9b53056b6c0))

- Keep function curves modelled beside a histogram or colour let
  ([#344](https://github.com/BenHuddart/gleplot/pull/344),
  [`686e613`](https://github.com/BenHuddart/gleplot/commit/686e61314b45b9a6ce952358e325c6ed719d1478))

- Keep generated subs a loaded file still needs, and edited ones
  ([`984a000`](https://github.com/BenHuddart/gleplot/commit/984a000534d625395ddd89e50430e06efd0580b1))

- Keep GLE's output in the missing-include message
  ([`b931fc3`](https://github.com/BenHuddart/gleplot/commit/b931fc32edd943f9a29ecfa4f6f15fad69c5147c))

- Keep mdist and deresolve on an error-bar dataset read from a file
  ([#343](https://github.com/BenHuddart/gleplot/pull/343),
  [`3342e24`](https://github.com/BenHuddart/gleplot/commit/3342e24a4faf43ef76e1d48dec3ad526ce24a21b))

- Keep minor ticks asked for on any axis, and none on a grid
  ([`836533e`](https://github.com/BenHuddart/gleplot/commit/836533e3693b4fb72f6b97fd7e735d1305b0f401))

- Keep new LaTeX preamble files while another script's cache folder exists
  ([`7b49caf`](https://github.com/BenHuddart/gleplot/commit/7b49caf92d1b3e5d9e0f4ddc547ac836fac35d7b))

- Keep only missing-value columns unconverted in shared sidecars
  ([`c005288`](https://github.com/BenHuddart/gleplot/commit/c0052884b1f792a430e621215d523d9bc094fab5))

- Keep only the files whose raw datasets would lose their definition
  ([`ee68ab7`](https://github.com/BenHuddart/gleplot/commit/ee68ab7525dd480795eb122c4441e6745060c5aa))

- Keep raw GLE between graph blocks after the graph it follows
  ([`70ec4fb`](https://github.com/BenHuddart/gleplot/commit/70ec4fbe65abf75093cfd3d975326de0e60b055c))

- Keep room for the top axis a raw x2axis line numbers
  ([`0846e84`](https://github.com/BenHuddart/gleplot/commit/0846e847f31d1072ee7d1ec2c8d4eafa1a5a8e55))

- Keep the edge an unsupported bar linestyle says it keeps
  ([`9f6c70e`](https://github.com/BenHuddart/gleplot/commit/9f6c70e92233c8dce57ad4ca790c90f224496efa))

- Keep the writer's blank after a regenerated sub out of raw GLE
  ([`5342e06`](https://github.com/BenHuddart/gleplot/commit/5342e06bebe8dc4ef4480c59eaa6a6b8cf74d897))

- Leave a label starting with an underscore out of the legend
  ([`f34c5dc`](https://github.com/BenHuddart/gleplot/commit/f34c5dca99db66994006f618ebc98ce96f35a2ec))

- Leave an unmasked or non-numeric masked array as it is
  ([`5bcc533`](https://github.com/BenHuddart/gleplot/commit/5bcc5330c915349733d69f4dae4c39c64a294848))

- Leave out a scatter point or bar whisker whose value is masked
  ([`c1288cc`](https://github.com/BenHuddart/gleplot/commit/c1288cc579e0f7ea7436099be896a432a35f4920))

- Leave out lw=0 segments and line modes silently; warn where no line can go
  ([`0bf76b0`](https://github.com/BenHuddart/gleplot/commit/0bf76b0418c2a9462eff9567ff6f4f9956f0e12b))

- Let alpha= win over a zero-alpha colour, and keep open drawings drawable
  ([`c93e75a`](https://github.com/BenHuddart/gleplot/commit/c93e75a857bb5a041305c094a89ad7d01f904e08))

- Limit .gle/ cleanup to the script's own folder and new preamble files
  ([`4bd5bc7`](https://github.com/BenHuddart/gleplot/commit/4bd5bc7cf6caa61099af6dc2123233cf3531e886))

- Line_from_file(linewidth=None) draws the default width
  ([`4cd0852`](https://github.com/BenHuddart/gleplot/commit/4cd0852933d08e6080fb5861f3636a168fc39caf))

- Match a kept comment by its line, not its text
  ([#382](https://github.com/BenHuddart/gleplot/pull/382),
  [`165e3bf`](https://github.com/BenHuddart/gleplot/commit/165e3bf1290b87fa19139f0197fcc593abb3058b))

- Match only calls of the polar and image subs in raw GLE
  ([`8e4bcf6`](https://github.com/BenHuddart/gleplot/commit/8e4bcf626e94d7b5221b29674ca9a8c70893d379))

- Model a file error bar the writer depends on, and name what it drops
  ([#188](https://github.com/BenHuddart/gleplot/pull/188),
  [`acadfa4`](https://github.com/BenHuddart/gleplot/commit/acadfa490174fa1082119e491f5b3d3f73172a06))

- Move gleplot's subs only ahead of a raw sub that calls them
  ([`5d8e2e3`](https://github.com/BenHuddart/gleplot/commit/5d8e2e308fd5815f6e684bfa182c57e7201d9936))

- Name an explicit cairo=True as the reason for the Cairo font warning
  ([`42a8b86`](https://github.com/BenHuddart/gleplot/commit/42a8b8686dbe6e1bccf1ac1fce8da3e2e0eeb57f))

- Name masked samples and infinite sizes in the scatter, bar and hist errors
  ([`cb11277`](https://github.com/BenHuddart/gleplot/commit/cb112779ae62081329a0ee6f904cdba3cd465f54))

- Name the argument that held an unrecognised colour
  ([`1892d10`](https://github.com/BenHuddart/gleplot/commit/1892d10b4083f2b76b6530146288e18d7b048537))

- Never rewrite a user's data file read by a fill or bar
  ([`1501f7a`](https://github.com/BenHuddart/gleplot/commit/1501f7ad52aafd09f5df81537ae6fcc20482bdf0))

- Normalise a data file's path without resolving it
  ([`626e16c`](https://github.com/BenHuddart/gleplot/commit/626e16cf7297233123576edf89cf71f71733d3fe))

- Note a let kept as raw GLE with the line that draws it
  ([#429](https://github.com/BenHuddart/gleplot/pull/429),
  [`c5602d7`](https://github.com/BenHuddart/gleplot/commit/c5602d738c379b3941a662e8544388692ce476a9))

- Note colorbars kept raw after 'end graph' instead of resetting or overwriting them
  ([`a5e3d6e`](https://github.com/BenHuddart/gleplot/commit/a5e3d6ee75710c01de438b6bcb5dfeb654035c34))

- Note every colorbar and contour-label group kept raw after a graph
  ([`d6cf795`](https://github.com/BenHuddart/gleplot/commit/d6cf795bc9562cb7d67c719b6191d0a7f9e8a836))

- Note every raw let raw GLE uses, once, after the block
  ([#429](https://github.com/BenHuddart/gleplot/pull/429),
  [`086d03a`](https://github.com/BenHuddart/gleplot/commit/086d03acb456afb0baee0fd5a62ea26ab0d9c3a1))

- One format resolver for plot, step and errorbar; keywords win
  ([`6a281f7`](https://github.com/BenHuddart/gleplot/commit/6a281f7f544da95a724f1aaa579f09c836fa89f3))

- Open_gle keeps files GLE reads differently as references
  ([#169](https://github.com/BenHuddart/gleplot/pull/169),
  [`9c6c852`](https://github.com/BenHuddart/gleplot/commit/9c6c8522e16d6948f3998c02ac0320a8c71fcd69))

- Open_gle maps columns by GLE's own reading of the data file
  ([`af71366`](https://github.com/BenHuddart/gleplot/commit/af713667f90c69df2cb1f875a6b12ee4334bdd55))

- Pair each legend key with its own graph's, on a copy of the figure
  ([`86fa8f4`](https://github.com/BenHuddart/gleplot/commit/86fa8f436886d5c942accd3f282728e395366746))

- Pass -cairo for every SVG compile, and warn when cairo=False is ignored
  ([`be3a4fa`](https://github.com/BenHuddart/gleplot/commit/be3a4fa307885f83ab129b4cb57817625dbe4f20))

- Place a tripcolor's grid nodes where tricontour places them
  ([`616652f`](https://github.com/BenHuddart/gleplot/commit/616652f8a467c8099427e1a285890db8e4c86863))

- Place an imshow grid's nodes where contour places them
  ([`9a99c83`](https://github.com/BenHuddart/gleplot/commit/9a99c83dd4f4b370536b5b229bd1b0ba908e9895))

- Raise for an unknown colour at the call
  ([`ea17104`](https://github.com/BenHuddart/gleplot/commit/ea17104597689595198e58c21a61a2585cf29b29))

- Raise when a two-curve file fill has no second column
  ([#403](https://github.com/BenHuddart/gleplot/pull/403),
  [`a2e6ba9`](https://github.com/BenHuddart/gleplot/commit/a2e6ba9e1cf994a74067922f5a76b387232d73a3))

- Read a band sub in either form, and reject one with no colour range
  ([`9d7f03f`](https://github.com/BenHuddart/gleplot/commit/9d7f03f6951040191afb4a6fe455a3745d184ab2))

- Read a masked value as NaN where matplotlib leaves it out
  ([`56becd5`](https://github.com/BenHuddart/gleplot/commit/56becd526217449e4f9355fb5eb06fe85a62cc8b))

- Read an error bar's errors from its own file under any spelling
  ([`82a38ad`](https://github.com/BenHuddart/gleplot/commit/82a38ad62fa417d8832448b0a059f1509d0ae998))

- Read an unmarked heatmap grid where colormap draws its nodes
  ([`901ea1f`](https://github.com/BenHuddart/gleplot/commit/901ea1f2f604c33952ea8ecd9b5f68bfd656105a))

- Read back every style default the writer records
  ([#345](https://github.com/BenHuddart/gleplot/pull/345),
  [`a844ebc`](https://github.com/BenHuddart/gleplot/commit/a844ebc565cd8138eb82d657da70c3889e987eee))

- Read errorbar xerr/yerr shapes as matplotlib does
  ([`70ee5ae`](https://github.com/BenHuddart/gleplot/commit/70ee5aeb7308c362a98dc1e033ad2615f916e815))

- Read GLE strings without backslash escapes, as GLE does
  ([`5407b0f`](https://github.com/BenHuddart/gleplot/commit/5407b0fbf59aca946a01f0d575688c282697e2a5))

- Read matplotlib format strings in plot, step and errorbar
  ([`0fef6aa`](https://github.com/BenHuddart/gleplot/commit/0fef6aa1dbec9370c815f36f9a9e06b1c868dce5))

- Read only as far as the layout needs, and note a file GLE stops on
  ([`940dc53`](https://github.com/BenHuddart/gleplot/commit/940dc53deea474bd074521edb9a51869d8df5842))

- Read only the subs gleplot writes; keep a glp_ sub of one's own
  ([`a1af3e8`](https://github.com/BenHuddart/gleplot/commit/a1af3e868acb962ae17c189eb6483d82b73e8ff8))

- Record a non-default default_linewidth so open_gle restores it
  ([#345](https://github.com/BenHuddart/gleplot/pull/345),
  [`228e9dd`](https://github.com/BenHuddart/gleplot/commit/228e9dd1d16711ebc5b65c925769d93c0f8d4ba0))

- Record default colours too, and report a malformed msize_scale
  ([#345](https://github.com/BenHuddart/gleplot/pull/345),
  [`f74d653`](https://github.com/BenHuddart/gleplot/commit/f74d653db46b1de05bbc8481a885534d065501c4))

- Reject a data_file holding a double quote at the call
  ([`7b4aa91`](https://github.com/BenHuddart/gleplot/commit/7b4aa9116ceb35d25d2c843d9fea16b8fc6000e2))

- Reject a masked imshow Z instead of drawing the value under the mask
  ([`6979659`](https://github.com/BenHuddart/gleplot/commit/6979659000313c00c283e83c6c464ef54d89d122))

- Reject a NaN or infinite axhline/axvline position at the call
  ([`9cbe42f`](https://github.com/BenHuddart/gleplot/commit/9cbe42ffde0c40c6f0702ec54339e53920182a97))

- Reject a NaN, infinite or negative linewidth on plot and line calls
  ([`2cad58c`](https://github.com/BenHuddart/gleplot/commit/2cad58ca5ef83f61bd427551d510274462908f55))

- Reject an axis= on set_xlabel/set_ylabel that names no axis
  ([`f76aa43`](https://github.com/BenHuddart/gleplot/commit/f76aa4301f2515df4beb71be0e296acc23516267))

- Reject an unknown file-fill target too ([#403](https://github.com/BenHuddart/gleplot/pull/403),
  [`0bbd386`](https://github.com/BenHuddart/gleplot/commit/0bbd3866ea8d00a60a593980afa70c441edbd843))

- Reject an unknown GLEGraphConfig scale_mode and warn on 'fixed'
  ([`8a8c0e5`](https://github.com/BenHuddart/gleplot/commit/8a8c0e583c878beeea9736a21d37c1ef5a48c059))

- Reject plot and errorbar data that does not pair up, at the call
  ([`3b019c9`](https://github.com/BenHuddart/gleplot/commit/3b019c9006336378ba8920c5259f5de2bfb6781d))

- Reject scatter x and y of different sizes at the call
  ([`983939f`](https://github.com/BenHuddart/gleplot/commit/983939f63caa838ee9d136ac606153429b55db62))

- Remove GLE's .gle/ LaTeX cache entries that a savefig compile created
  ([`1c4259a`](https://github.com/BenHuddart/gleplot/commit/1c4259a2039d676571539fd2b4d2596d2c3e3f7b))

- Replace undecodable bytes in GLE's output instead of raising
  ([`db5e2b4`](https://github.com/BenHuddart/gleplot/commit/db5e2b4b2f2c9ee34548944c34a3dd21363c8afd))

- Report a comment after a statement open_gle models
  ([#382](https://github.com/BenHuddart/gleplot/pull/382),
  [`4749e56`](https://github.com/BenHuddart/gleplot/commit/4749e569fbcc34c3e2aa55ab3b4e47c8419118b3))

- Report a contour block line that open_gle drops
  ([#176](https://github.com/BenHuddart/gleplot/pull/176),
  [`901a617`](https://github.com/BenHuddart/gleplot/commit/901a617d47e538627154b457b826701df451cdaa))

- Report a fitz block line that open_gle drops
  ([#380](https://github.com/BenHuddart/gleplot/pull/380),
  [`0917834`](https://github.com/BenHuddart/gleplot/commit/0917834745a43e3120de395dc880a2b5a35a1937))

- Report an 'end sub' or 'end if' with nothing open to close
  ([#189](https://github.com/BenHuddart/gleplot/pull/189),
  [`c94a1b8`](https://github.com/BenHuddart/gleplot/commit/c94a1b84ac4235470261d8e3fa5b568b76451097))

- Report each unloaded file once per graph ([#169](https://github.com/BenHuddart/gleplot/pull/169),
  [`999ad44`](https://github.com/BenHuddart/gleplot/commit/999ad44823a8ee09e2ef47a7e27b08f7f8254f3b))

- Report everything a contour's dataset line loses on load
  ([#296](https://github.com/BenHuddart/gleplot/pull/296),
  [`39e72f0`](https://github.com/BenHuddart/gleplot/commit/39e72f017bae5c4f240df04a91ebc5d863f987e4))

- Resolve text aliases per call, keep grid on for any keyword, and more
  ([`958d60e`](https://github.com/BenHuddart/gleplot/commit/958d60e0d80e2159845b348819be89762fb771dd))

- Review fixes for data-statement recovery ([#169](https://github.com/BenHuddart/gleplot/pull/169),
  [`fb688d9`](https://github.com/BenHuddart/gleplot/commit/fb688d9d36270b8a85e85b14b1ee55845a9ea498))

- Review fixes for the contourf colorbar ([#258](https://github.com/BenHuddart/gleplot/pull/258),
  [`dda46d2`](https://github.com/BenHuddart/gleplot/commit/dda46d2ea1b339c17b2b45caf260a896726122b6))

- Review fixes for the data-range edges ([#343](https://github.com/BenHuddart/gleplot/pull/343),
  [`276415d`](https://github.com/BenHuddart/gleplot/commit/276415d5dba2005f44965cb33086a152c159282d))

- Review fixes for the primary y autoscale ([#142](https://github.com/BenHuddart/gleplot/pull/142),
  [`f24170f`](https://github.com/BenHuddart/gleplot/commit/f24170f97504c7e2d046bc91c7410aafc153c907))

- Say what to pass when scatter x and y differ in size
  ([`76e4ae6`](https://github.com/BenHuddart/gleplot/commit/76e4ae69eb85b34d51f424616d5262072f39ef20))

- Set_xlim/set_ylim reject a bad axis or a non-finite limit
  ([`de9806b`](https://github.com/BenHuddart/gleplot/commit/de9806b6d3c9c0f03d5a489158959052490bfd4a))

- Set_xlim/set_ylim take only numbers or None as limits
  ([`fefa13c`](https://github.com/BenHuddart/gleplot/commit/fefa13c093282226031d47d19ce5d25bc3497082))

- Share a data file only where its columns allow it
  ([`69c9e8d`](https://github.com/BenHuddart/gleplot/commit/69c9e8d00c09bbc57bf8e7ee9aebaa01b78d31f4))

- Sharex/sharey honour matplotlib's 'all', 'none', 'row' and 'col'
  ([`6719ae0`](https://github.com/BenHuddart/gleplot/commit/6719ae068aea228e48dd0a24f03365e0b1527063))

- Stop reporting 'end sub' and 'end if' as an 'end' without a 'begin'
  ([#189](https://github.com/BenHuddart/gleplot/pull/189),
  [`d94363b`](https://github.com/BenHuddart/gleplot/commit/d94363bcfba3ac9dba20a4212e677c4a7dd7b31f))

- Stroke a bar with no edge in the colour under it
  ([`4611e51`](https://github.com/BenHuddart/gleplot/commit/4611e5105aaa222a35806f292099fedd50989e15))

- Take a positional dict or None in set_xlabel's axis place as fontdict
  ([`57f4de8`](https://github.com/BenHuddart/gleplot/commit/57f4de84291f1257eeb6c7115c57ab5d88d801c3))

- Take a positional fontdict on the twin views' own label setters too
  ([`b3f7317`](https://github.com/BenHuddart/gleplot/commit/b3f7317adc12a81db5acd9e8d76c51a9446abf3d))

- Take colors=None as the default in contour and tricontour too
  ([`2f03f9a`](https://github.com/BenHuddart/gleplot/commit/2f03f9a5c1a87d7f73a79431437f7383816ed096))

- Take matplotlib's scalar, column and (2, N) forms in plot and errorbar
  ([`27e1359`](https://github.com/BenHuddart/gleplot/commit/27e1359d1af7e5be8888ca34cf4a0753bcdbac41))

- Treat a.dat and ./a.dat as one file when opening a GLE file
  ([`e8c2b53`](https://github.com/BenHuddart/gleplot/commit/e8c2b53895e336a5db8b25c6cac51254a5ef45c7))

- Treat markerfacecolor/mfc and drawstyle/ds conflicts like the other aliases
  ([`981e6ab`](https://github.com/BenHuddart/gleplot/commit/981e6ab04bc428d23d8b305aa954fc398e7cd495))

- Type the data-range edge check so mypy passes
  ([#343](https://github.com/BenHuddart/gleplot/pull/343),
  [`274a207`](https://github.com/BenHuddart/gleplot/commit/274a2075b54208d1bfd4314a0a0a362b17e602cd))

- Warn about a 'none' bar face whose edge style is 'none' too
  ([`f95c8f4`](https://github.com/BenHuddart/gleplot/commit/f95c8f45e100f00dc3a1cc9f8daa8a1938649595))

- Warn at save when a data range leaves GLE nothing to draw
  ([#343](https://github.com/BenHuddart/gleplot/pull/343),
  [`bd040cd`](https://github.com/BenHuddart/gleplot/commit/bd040cdac6d790c502a37f32a3f3103ed08db94d))

- Warn rather than raise or mis-route for three more inputs
  ([`0843039`](https://github.com/BenHuddart/gleplot/commit/0843039c1cd044a2c95edaf20b7446ac769eef38))

- Warn when a line has negative values on a log axis
  ([`539518c`](https://github.com/BenHuddart/gleplot/commit/539518cfb856172ee89a4a2ca7e5638e451d6f8b))

- Write a band's edges as its fill does; ftick and rugs on the axis
  ([`bdbf367`](https://github.com/BenHuddart/gleplot/commit/bdbf367d06620071a10eafcb1e37a6796ce08ab5))

- Write a bar's 'none' face as GLE's CLEAR fill
  ([`96c82a4`](https://github.com/BenHuddart/gleplot/commit/96c82a465510272d234217967474a77d80a42720))

- Write a lineless file reference through the one line path
  ([`23205f6`](https://github.com/BenHuddart/gleplot/commit/23205f6017621361bca2a1734208775f4dfb730a))

- Write a sidecar named two ways, such as a.dat and ./a.dat, once
  ([`1eaafab`](https://github.com/BenHuddart/gleplot/commit/1eaafabfa95eef43b47b7b6ad5e0993a0d50b81c))

- Write dropped points as missing in provider-backed sized scatters
  ([`bc551d9`](https://github.com/BenHuddart/gleplot/commit/bc551d9b8673c6ee74a68c48345ce0916f7b0a3b))

- Write gleplot's subs ahead of a kept raw sub that calls them
  ([`3d2cb24`](https://github.com/BenHuddart/gleplot/commit/3d2cb243838da391b1942389fd09baad10735acb))

- Write text holding a double quote in a form GLE compiles
  ([`4681cd1`](https://github.com/BenHuddart/gleplot/commit/4681cd150a0d0bdc93d81848138353f8c83c8fd7))

- Write the polar or image sub a raw GLE call still needs
  ([`cd7302f`](https://github.com/BenHuddart/gleplot/commit/cd7302f865537dc560032b940837e4f96b7af26e))

- Write two bars on one loaded sidecar back into that file
  ([`f3b06cd`](https://github.com/BenHuddart/gleplot/commit/f3b06cd1618ef91a6387acc13a44b0771c56dfc2))

- **colorbar**: Label the zero tick 0.0, not -0.0, when ticks cross zero
  ([`a0301e3`](https://github.com/BenHuddart/gleplot/commit/a0301e39c478c8429ccd61039468c24a920262e9))

- **parser**: Keep a .z colormap raw when a clause would not round-trip
  ([`294c02b`](https://github.com/BenHuddart/gleplot/commit/294c02b4877ae66ec15b3ed4a8e9f6bce7a6567b))

- **parser**: Keep a blank line after the last graph when an amove follows
  ([`9d2064d`](https://github.com/BenHuddart/gleplot/commit/9d2064d804df55c886e96b9d46015ab4671aa7d1))

- **parser**: Keep key hei/nobox when the key line has no pos
  ([`7bad374`](https://github.com/BenHuddart/gleplot/commit/7bad374c7346b96b8956f32ae0143cb676f59f82))

- **parser**: Keep the height on a combined 'set font X hei Y' line
  ([`319edf7`](https://github.com/BenHuddart/gleplot/commit/319edf78556a395c8cd4cd01190efe0f86f8b7c7))

- **parser**: No 'mixes datasets' note for columns nothing reads
  ([`bca2e11`](https://github.com/BenHuddart/gleplot/commit/bca2e113baecda5011340c863690bdb314825957))

- **parser**: Read back a begin key that lists function, derived or hist curves
  ([`86df898`](https://github.com/BenHuddart/gleplot/commit/86df898261ca43513eb6ac3a2cd90bd1bbf6ee1f))

- **parser**: Report a comment dropped from the commands after end graph
  ([`47976e1`](https://github.com/BenHuddart/gleplot/commit/47976e1cd09dd458bd81471a1e0b8360bbdb9b9f))

- **text**: Warn when a texcm font will draw text characters as other glyphs
  ([`c861700`](https://github.com/BenHuddart/gleplot/commit/c86170072abf236f4db5f7b0f9b2132afbddd7d6))

### Chores

- Ignore throwaway .venv-* environments
  ([`c888903`](https://github.com/BenHuddart/gleplot/commit/c888903b08ddd1210eca9a2bcac191c04d5a008a))

### Code Style

- Black the subplots example
  ([`f0a422e`](https://github.com/BenHuddart/gleplot/commit/f0a422ed58107bf387b2f63038d706d2c9e250ee))

- Format the #512 test
  ([`a4d7601`](https://github.com/BenHuddart/gleplot/commit/a4d76010a4f1cd864afa9c189df6e5e6a262c5e7))

- Format the #528 test
  ([`955c142`](https://github.com/BenHuddart/gleplot/commit/955c1425d998db40457bfd187eadb841e5e80d24))

### Continuous Integration

- Install Windows Ghostscript from the pinned official installer
  ([`a5c974b`](https://github.com/BenHuddart/gleplot/commit/a5c974bd4d2ca03c52344889a1a04e2f2d511fcd))

- Pin Windows Ghostscript to 10.07.1 and log the install steps
  ([`3d1ba22`](https://github.com/BenHuddart/gleplot/commit/3d1ba22588075101485badf0b2ce127b436e7061))

- Unpack Windows Ghostscript with 7-Zip instead of installing it
  ([`c8a8e55`](https://github.com/BenHuddart/gleplot/commit/c8a8e55d7464984270e4085a3e49aba76c1f264e))

### Documentation

- Add a 6.0 migration page and review the guides and README for 6.0
  ([`fb0f767`](https://github.com/BenHuddart/gleplot/commit/fb0f76725f1ac8e9cd692ccc0ba37fbe08da73ed))

- Add gallery examples for basic plot types without one
  ([`bfd2362`](https://github.com/BenHuddart/gleplot/commit/bfd2362180272c3359da8c26912a416d83fa19f8))

- Add gallery examples for figure-level and layout features
  ([`06dd239`](https://github.com/BenHuddart/gleplot/commit/06dd2395d7c29d4c66de8d6551fa49f63493c80b))

- Address review of AGENTS.md scope and release policy
  ([`3bdd762`](https://github.com/BenHuddart/gleplot/commit/3bdd762b1297e734bb8c4769390bbddd22cff1a7))

- Align the versioning guide, docs index and package metadata with the 6.0 plan
  ([#349](https://github.com/BenHuddart/gleplot/pull/349),
  [`d95537c`](https://github.com/BenHuddart/gleplot/commit/d95537c2d45b53fb89688f6d1e50b7b48d7573b4))

- Correct captions and ranges in the new figure-level examples
  ([`45d17ec`](https://github.com/BenHuddart/gleplot/commit/45d17ec6826a438c98518e5df12ab36963cbf25b))

- Describe dN xmin/xmax/ymin/ymax as a data range, not a clip window
  ([#329](https://github.com/BenHuddart/gleplot/pull/329),
  [`5147c5b`](https://github.com/BenHuddart/gleplot/commit/5147c5b4a1ac626d0ec8e2cc8e4076125c96ba08))

- Keep a wrapped '1.' from starting a list ([#391](https://github.com/BenHuddart/gleplot/pull/391),
  [`90eb30a`](https://github.com/BenHuddart/gleplot/commit/90eb30a02ded27c133f8e0658410174b78b4dda4))

- Load the gallery faster with sized, lossless WebP images
  ([`111a56c`](https://github.com/BenHuddart/gleplot/commit/111a56cac1dfc8685404acfbaf52cb664cf98b62))

- Name the axis an omitted range edge takes, and the tick-label effect
  ([#329](https://github.com/BenHuddart/gleplot/pull/329),
  [`b48f188`](https://github.com/BenHuddart/gleplot/commit/b48f1881af3601b65987e8c90291a7a2e3101163))

- Name the guides that keep 6 figures
  ([`4eb8576`](https://github.com/BenHuddart/gleplot/commit/4eb8576961b81ec7e523bd41a2e875dba5a1435e))

- Note broken-axis segments and twin views in Figure.axes
  ([#136](https://github.com/BenHuddart/gleplot/pull/136),
  [`2ccc3ad`](https://github.com/BenHuddart/gleplot/commit/2ccc3ad9424bd13bd03e40c31101bac78d945ca7))

- Record GLE-first scope and gathered-major release policy
  ([`6297384`](https://github.com/BenHuddart/gleplot/commit/6297384248fc3071927273bf5d5ba9249a3a0519))

- Require a gallery example for new plot types and features
  ([`c041a2e`](https://github.com/BenHuddart/gleplot/commit/c041a2e95feb6ac42fd50154eae3c9db612fa8e1))

- Review fixes for the reference-line alpha note
  ([#391](https://github.com/BenHuddart/gleplot/pull/391),
  [`f4616f7`](https://github.com/BenHuddart/gleplot/commit/f4616f7d1d2c838f5e1e490ce9ea180343a73cc0))

- Review fixes for the versioning guide and package description
  ([#349](https://github.com/BenHuddart/gleplot/pull/349),
  [`cc14ce5`](https://github.com/BenHuddart/gleplot/commit/cc14ce5558673f2dad720a6e36091dd3540acc2e))

- Say a contour line's unset colour and width write no keyword
  ([`e68f0ed`](https://github.com/BenHuddart/gleplot/commit/e68f0ed9cec37c8771bea0933ff7b57169c7ebdc))

- Say how the colour-mapped scatter's colours reach GLE
  ([`04e1ecd`](https://github.com/BenHuddart/gleplot/commit/04e1ecd9f4505efdb551af19c9d4c0012d198997))

- Say per-point colours with per-point sizes now warn and draw at one size
  ([`a28d025`](https://github.com/BenHuddart/gleplot/commit/a28d0258507c4675b45881266223175d59f811f1))

- Say that a labelled axes draws its legend without legend()
  ([`c0997f3`](https://github.com/BenHuddart/gleplot/commit/c0997f335ac351d3980fefd9b8ee8301e2a1ff59))

- Say what reference-line and span alpha do now
  ([#391](https://github.com/BenHuddart/gleplot/pull/391),
  [`cf7994c`](https://github.com/BenHuddart/gleplot/commit/cf7994c4069624b283ab8e8bfecaf46e86849c21))

### Features

- Accept one bar width per bar in bar() and barh()
  ([`5460fec`](https://github.com/BenHuddart/gleplot/commit/5460fec6ef68a5aa53354e4eb69eed65d60a14f1))

- Accept per-level linewidths/linestyles lists in contour and tricontour
  ([`3d2d441`](https://github.com/BenHuddart/gleplot/commit/3d2d441462fbd4fef5032740279faeb68b98f7b3))

- Add matplotlib's read-only Figure.axes list
  ([#136](https://github.com/BenHuddart/gleplot/pull/136),
  [`35ceed8`](https://github.com/BenHuddart/gleplot/commit/35ceed843c30d09b0247b18f1df101693e9f1097))

- Axes.set_facecolor and add_axes(facecolor=) as GLE's graph background
  ([#240](https://github.com/BenHuddart/gleplot/pull/240),
  [`eef4225`](https://github.com/BenHuddart/gleplot/commit/eef422523c0684004e4f75acfbe660dd57de1912))

- Close() accepts 'all', as matplotlib's pyplot.close
  ([`b6a4204`](https://github.com/BenHuddart/gleplot/commit/b6a4204094c9689485926ced9e52e85d651ddfd1))

- Draw a bar with no edge unless one is asked for
  ([`90d5007`](https://github.com/BenHuddart/gleplot/commit/90d50075549677fe5d5f37fc86ad5ef627efde4a))

- Draw colorbars with GLE's color.gle
  ([`74aeb9c`](https://github.com/BenHuddart/gleplot/commit/74aeb9c9d08df6aa3f3c5bc890a18210932b3015))

- Draw colormaps with GLE's palettes.gle and color.gle
  ([`fb6e341`](https://github.com/BenHuddart/gleplot/commit/fb6e341b0632d64ac712424c38263a5139c8b5ac))

- Draw engine-range guides with GLE's graphutil.gle after the graph
  ([`2e0a7ac`](https://github.com/BenHuddart/gleplot/commit/2e0a7ac3620db4c40d1895ba9582194bd3591a8c))

- Draw rugs with GLE's rugs.gle
  ([`b19a533`](https://github.com/BenHuddart/gleplot/commit/b19a533feecf2dacc19fd66a0e8dd993b02b6764))

- Draw the ColorBrewer colormaps with GLE's brewer.gle
  ([`4e0ad67`](https://github.com/BenHuddart/gleplot/commit/4e0ad67cac7de670415e7e2f5d93511112a09abe))

- Drop gleplot 5 file compatibility; name generated subs glp_
  ([`d60ae54`](https://github.com/BenHuddart/gleplot/commit/d60ae54b10fc4b8e2ee70fda1a12a1c216e20e66))

- Errorbar_from_file takes the data range xmin..ymax
  ([#343](https://github.com/BenHuddart/gleplot/pull/343),
  [`f969121`](https://github.com/BenHuddart/gleplot/commit/f969121a7e0cfc76e8b1c617856720a298a61550))

- Give bar matplotlib's positional order, bar(x, height, width, bottom)
  ([`237d531`](https://github.com/BenHuddart/gleplot/commit/237d5318b5f2a5739884392bd260ca09ea1a849c))

- Give each axes matplotlib's C0-C9 colour cycle
  ([`8c2e374`](https://github.com/BenHuddart/gleplot/commit/8c2e3744b43da0ab07676b8827fa1774408f1e86))

- Give errorbar the dN xmin/xmax/ymin/ymax data range
  ([#168](https://github.com/BenHuddart/gleplot/pull/168),
  [`d4247c1`](https://github.com/BenHuddart/gleplot/commit/d4247c1e895835a3406150aebe3bee378f02e2d9))

- Give scatter matplotlib's positional order, scatter(x, y, s, c)
  ([`f02b57d`](https://github.com/BenHuddart/gleplot/commit/f02b57dda61bacae6b66adad63c431fe5f09d640))

- Keep the colour cycle in to_dict and count it once per call on load
  ([`f97d886`](https://github.com/BenHuddart/gleplot/commit/f97d8863475fd3dff8b6106ffd1e176f2d16ed54))

- Name GLE's own words in the error-bar qualifier note
  ([#168](https://github.com/BenHuddart/gleplot/pull/168),
  [`b97e30d`](https://github.com/BenHuddart/gleplot/commit/b97e30de574223598b186e6fd5356ef39ca661c4))

- Name the new order when a colour lands in scatter's s, and check scalar sizes
  ([`cc8416d`](https://github.com/BenHuddart/gleplot/commit/cc8416df5dba215d296236d84d73c9f7973f3eb8))

- Pass text keywords through glp and Figure label and title wrappers
  ([`420ed3f`](https://github.com/BenHuddart/gleplot/commit/420ed3ffe905a08da0f7b597eff778e93bdd1561))

- Reject an x2 title on a broken x-axis and name the gap to set
  ([`3c99bde`](https://github.com/BenHuddart/gleplot/commit/3c99bdeab56a7efee31e6bec40472bc34071d7b5))

- Remove BrokenAxes
  ([`bbef0e6`](https://github.com/BenHuddart/gleplot/commit/bbef0e685e1e002a0eed1efd0523b15f1dc2b091))

- Remove GLEWriter's deprecated per-field keyword methods
  ([#100](https://github.com/BenHuddart/gleplot/pull/100),
  [`5530b43`](https://github.com/BenHuddart/gleplot/commit/5530b437c870521be3d6c042076cbacc2207313c))

- Remove pie and boxplot
  ([`157e216`](https://github.com/BenHuddart/gleplot/commit/157e2162db3f0d1b48469ce38050fe9ea260c8aa))

- Require GLE's include library and name a missing include
  ([`e004eb9`](https://github.com/BenHuddart/gleplot/commit/e004eb9515b09228f933f8fa8cce3d5854fbb03e))

- Review fixes for the axes facecolor ([#240](https://github.com/BenHuddart/gleplot/pull/240),
  [`0222afa`](https://github.com/BenHuddart/gleplot/commit/0222afae759c60becabd35f63e05c75c6f765673))

- Set_xlim/set_ylim return the new (low, high) limits
  ([`56e913d`](https://github.com/BenHuddart/gleplot/commit/56e913d7906d4e34ad58cdf259ce6a5efa21881b))

- Set_xlim/set_ylim take matplotlib's left/right and bottom/top
  ([`4e16ed0`](https://github.com/BenHuddart/gleplot/commit/4e16ed01e4ab8fc4dc4070dc6e3761a2ac5a1857))

- Subplots takes only nrows and ncols positionally, as matplotlib
  ([`ed82a0f`](https://github.com/BenHuddart/gleplot/commit/ed82a0fba1a1cf9ad20dc04ecb2fce5ff891ded8))

- Subplots takes subplot_kw, gridspec_kw and figure keywords
  ([`5a3d495`](https://github.com/BenHuddart/gleplot/commit/5a3d495ecc936547055934f41133061cb5f2f753))

- Subplots() returns matplotlib's numpy array of Axes, with squeeze
  ([`0189fc4`](https://github.com/BenHuddart/gleplot/commit/0189fc46e007cdac93c22ba490095be6ed8df565))

- Take fontdict on set_xlabel/set_ylabel and y on glp.title
  ([`f0ffcf4`](https://github.com/BenHuddart/gleplot/commit/f0ffcf4082e8280399cceece8cad85ebc04b8857))

- Take text keywords on the broken-axis title setters
  ([`567a1fc`](https://github.com/BenHuddart/gleplot/commit/567a1fc844de5225cd2b8d958957cd15af19c0a7))

- Warn only for differing per-level contour values; resolve them per keyword
  ([`e8aacc8`](https://github.com/BenHuddart/gleplot/commit/e8aacc88df77d07ca508280665d0dd87cb3cc122))

- Write a colorbar's label beside its color.gle bar
  ([`dd6fabc`](https://github.com/BenHuddart/gleplot/commit/dd6fabcd254312ccbac1d821f167e9a6d7aa0774))

- Write contour labels with GLE's contour.gle
  ([`2400a27`](https://github.com/BenHuddart/gleplot/commit/2400a27a0dae5c2b4d135b776e7da436b51d92e3))

### Refactoring

- Drop the always-true legend.show test from the external-key branch
  ([`b2b364d`](https://github.com/BenHuddart/gleplot/commit/b2b364de7503cef8b6024fd3e81f2473e4410db5))

- Let legend_column_breaks own the one-column case
  ([`ac51864`](https://github.com/BenHuddart/gleplot/commit/ac518646ba8f1a6f613651e9d9411ba528a19d69))

- Share the line-mode/no-line check between plot and line_from_file
  ([`2ff2d5f`](https://github.com/BenHuddart/gleplot/commit/2ff2d5fbcec051cacb21f0c60c31f583a16ef344))

- State the line-mode rule without a writer detail that differs per caller
  ([`b0a28c0`](https://github.com/BenHuddart/gleplot/commit/b0a28c0034d3b63bd1cbcb2e4a53afd375bfa3c1))

### Testing

- A lineless guide is linestyle 'none'/'None'/'', not None
  ([`76d17fa`](https://github.com/BenHuddart/gleplot/commit/76d17fafc2e9bb604a1fadbdda7ec25aa1e12f25))

- A lineless guide is linestyle 'none'/'None'/'', not None
  ([`dba1aff`](https://github.com/BenHuddart/gleplot/commit/dba1aff8dd369d10cea8419ec5033e0a02eca8b3))

- Cover a derived curve beside a histogram let
  ([#344](https://github.com/BenHuddart/gleplot/pull/344),
  [`cd77194`](https://github.com/BenHuddart/gleplot/commit/cd7719462e374f60a00233271b0e8ff39ced9933))

- Cover twiny(delta_zorder=...) and type the twin keyword helper
  ([`7004c5d`](https://github.com/BenHuddart/gleplot/commit/7004c5d8875e6f56c75cb5b1ced3ab34694e476d))

- Do not create a quoted filename, which Windows forbids
  ([`e68055a`](https://github.com/BenHuddart/gleplot/commit/e68055a62253a3bbfc0f5dd4ba55c92e9f94344e))

- Drop a colorbar label the merged contourf builder passed
  ([`26af435`](https://github.com/BenHuddart/gleplot/commit/26af43551c60efe38f1eabe8d898817b9bc51c43))

- Expect the edgeless bar in the bar snapshots and digests
  ([`650e19a`](https://github.com/BenHuddart/gleplot/commit/650e19a0dfa33b8cefa251800700d3da4fdd15dd))

- Keep a gleplot 5 contour-label sub raw; refresh stale docstrings
  ([`1cd06e3`](https://github.com/BenHuddart/gleplot/commit/1cd06e32c81caac2cd24b92bce393ffbcf1d02c0))

- Keep heatmap fixtures within their grids
  ([`89300d7`](https://github.com/BenHuddart/gleplot/commit/89300d73f6e666a81ba1e0b4a4ab1753318d4445))

- Pin a lone comment between two subplots
  ([`4addb49`](https://github.com/BenHuddart/gleplot/commit/4addb49372baaa53002871dd190cecc176a79a96))

- Pin a raw line's err read of a renumbered error-bar dataset
  ([`bf6c812`](https://github.com/BenHuddart/gleplot/commit/bf6c8125f2652883aa256cae28068345dee300aa))

- Pin has_y2_plots counting a file series on y2
  ([`620604a`](https://github.com/BenHuddart/gleplot/commit/620604a37d9d53191305876ca2d43c0c33681b44))

- Pin that a raw function let keeps its dataset name
  ([#171](https://github.com/BenHuddart/gleplot/pull/171),
  [`240431d`](https://github.com/BenHuddart/gleplot/commit/240431d11ffa6b195f01bd433410c6c5381884be))

- Pin that begin keys listing hist and function curves are read back
  ([`e596341`](https://github.com/BenHuddart/gleplot/commit/e596341e6284641b03e4e52efaa94cfb07bccedf))

- Pin that non-finite svg_smooth and lstyle keep the line raw
  ([#167](https://github.com/BenHuddart/gleplot/pull/167),
  [`52d15d4`](https://github.com/BenHuddart/gleplot/commit/52d15d4a1a274c843d2e6f00fb6a4c6374ab9b87))

- Pin the fixed point for raw mdata naming a modelled dataset
  ([`180180f`](https://github.com/BenHuddart/gleplot/commit/180180fffb8f495b28df7b7d54379d225a7d837a))

- Point comments at the series entry points that replaced the wrappers
  ([#100](https://github.com/BenHuddart/gleplot/pull/100),
  [`7cb34c2`](https://github.com/BenHuddart/gleplot/commit/7cb34c2396878237ef5ffd8df3cd2b7fbfc6f21b))

- Require a note for an after-graph guide near miss kept raw
  ([`a0699ad`](https://github.com/BenHuddart/gleplot/commit/a0699ad561f75add07d742c9f3b68989009ef304))


## v5.6.3 (2026-11-19)

### Bug Fixes

- Draw matplotlib's named line styles and warn on undrawable ones
  ([`035fc06`](https://github.com/BenHuddart/gleplot/commit/035fc06e2f8fe7544b092baab768c54e2b40b1e6))

- Give scatter() matplotlib's marker=None default
  ([`e539380`](https://github.com/BenHuddart/gleplot/commit/e539380f1aaf553a839ec5375b13966be76510c0))

- Keep a dN line with unmodelled qualifiers as raw GLE
  ([`22be88c`](https://github.com/BenHuddart/gleplot/commit/22be88ccbcc113fcf69bf211ea4d4350c5ee7fc1))

- Keep a stored colour equal across a to_dict JSON round trip
  ([#273](https://github.com/BenHuddart/gleplot/pull/273),
  [`18d9132`](https://github.com/BenHuddart/gleplot/commit/18d9132a9538141a650d86d46a356c14783e233a))

- Keep raised columns from zeroing values and cover heatmap extents and log limits
  ([#250](https://github.com/BenHuddart/gleplot/pull/250),
  [`db845de`](https://github.com/BenHuddart/gleplot/commit/db845de70c5ada17da63318552e9c36bf7e2601a))

- Keep view()'s output for every format and tolerate locked work files
  ([`7bb2d3e`](https://github.com/BenHuddart/gleplot/commit/7bb2d3e7c503e785d63adc1fd8c230faa39d48a8))

- Map named line styles in contour and keep (offset, None) solid
  ([`fee1164`](https://github.com/BenHuddart/gleplot/commit/fee11643132b5d1106fa8556acb23a24902bad1b))

- Model the series and report what is dropped where a raw dN line would break
  ([#165](https://github.com/BenHuddart/gleplot/pull/165),
  [`323e64b`](https://github.com/BenHuddart/gleplot/commit/323e64b1a501c668428a759a5726b85eaf432a1c))

- Remove view()'s script, sidecars and GLE work files after compiling
  ([`1380d76`](https://github.com/BenHuddart/gleplot/commit/1380d76f625afa454e8bd3fd52a66fc1a23e08c0))

- Scatter(marker=None) draws matplotlib's default circle
  ([`df36b8c`](https://github.com/BenHuddart/gleplot/commit/df36b8cd4a7f42ac28b0e726114d8129819db7b2))

- Store an array colour in the style config or a broken axes as a tuple
  ([#273](https://github.com/BenHuddart/gleplot/pull/273),
  [`4ad3631`](https://github.com/BenHuddart/gleplot/commit/4ad3631aa3edf862d383f598e0b9bd1f89dbd568))

- Write data columns and axis ranges at the precision their values need
  ([#250](https://github.com/BenHuddart/gleplot/pull/250),
  [`4829c4c`](https://github.com/BenHuddart/gleplot/commit/4829c4cf86dd9b172790c32bcbff8c495906067f))


## v5.6.2 (2026-11-19)

### Bug Fixes

- Alpha= overrides an RGBA colour's alpha without a warning
  ([#267](https://github.com/BenHuddart/gleplot/pull/267),
  [`5b79a9f`](https://github.com/BenHuddart/gleplot/commit/5b79a9ff574894ac380f4f477ccdab57a5d31405))

- Errorbar, axvline/axhline and axvspan/axhspan honour aliases and warn on ignored keywords
  ([#233](https://github.com/BenHuddart/gleplot/pull/233),
  [`90f5e34`](https://github.com/BenHuddart/gleplot/commit/90f5e34ad5188b5673c59cd8feae9d5a3ca2eda1))

- Imshow, contour, tripcolor and tricontour warn on keywords they ignore
  ([#177](https://github.com/BenHuddart/gleplot/pull/177),
  [`b381cd5`](https://github.com/BenHuddart/gleplot/commit/b381cd55a6a2b782b4fb6b5cf004041b038f8154))

- Model only tick intervals the writer writes back unchanged
  ([#155](https://github.com/BenHuddart/gleplot/pull/155),
  [`666edec`](https://github.com/BenHuddart/gleplot/commit/666edec8bbb4b8b7e45539d05f3dfcf5268b0edf))

- Open_gle raises each recovery note as a UserWarning
  ([`0135197`](https://github.com/BenHuddart/gleplot/commit/0135197e057ec99ca33d09c448cec15e6c7344c8))

- Open_gle recovers dticks/dsubticks onto the axes
  ([`7406745`](https://github.com/BenHuddart/gleplot/commit/74067459a6143bafab0a559d658c111973bacc77))

- Review fixes for contour keyword aliases ([#177](https://github.com/BenHuddart/gleplot/pull/177),
  [`03c13ce`](https://github.com/BenHuddart/gleplot/commit/03c13ce7fa4df51c41cc8ee058c2c6dbe919af9b))

- Review fixes for errorbar and span keyword aliases
  ([#233](https://github.com/BenHuddart/gleplot/pull/233),
  [`e209677`](https://github.com/BenHuddart/gleplot/commit/e2096772c4355ef5369b8891277393cc6bceb284))

- Review fixes for open_gle recovery warnings
  ([#135](https://github.com/BenHuddart/gleplot/pull/135),
  [`db5eed7`](https://github.com/BenHuddart/gleplot/commit/db5eed761f3bb996d30f3ceb4ab82e99ae058e67))

- Review fixes for savefig keyword warnings ([#183](https://github.com/BenHuddart/gleplot/pull/183),
  [`0a66f21`](https://github.com/BenHuddart/gleplot/commit/0a66f219dc109ea493409228e7eac7bc742289bb))

- Savefig warns on keywords it ignores ([#183](https://github.com/BenHuddart/gleplot/pull/183),
  [`a5ee4b6`](https://github.com/BenHuddart/gleplot/commit/a5ee4b68272a7ea7f75f4b841c411ce32d02e847))

- Warn when a colour silently becomes BLACK or loses its alpha
  ([#267](https://github.com/BenHuddart/gleplot/pull/267),
  [`7132d7a`](https://github.com/BenHuddart/gleplot/commit/7132d7a84b7ea9a3924cdaca391d3fa17d8db918))

### Continuous Integration

- Add a Windows leg with GLE to the test job
  ([#102](https://github.com/BenHuddart/gleplot/pull/102),
  [`4e69f91`](https://github.com/BenHuddart/gleplot/commit/4e69f918cf6f0f119da95dfd5b9b194afdc8713e))

- Put Ghostscript on PATH for the Windows GLE leg
  ([#102](https://github.com/BenHuddart/gleplot/pull/102),
  [`9ef1780`](https://github.com/BenHuddart/gleplot/commit/9ef1780b4b42ebafd485e40051ad9bf58c1e2606))

- Scope Git Bash to the steps that need it ([#102](https://github.com/BenHuddart/gleplot/pull/102),
  [`92645de`](https://github.com/BenHuddart/gleplot/commit/92645ded699cf40458732739f6d2d00177cbd50f))

### Documentation

- Address review of the scale_mode docs ([#131](https://github.com/BenHuddart/gleplot/pull/131),
  [`8d47cc3`](https://github.com/BenHuddart/gleplot/commit/8d47cc3b6d86ccaca87136c1c0de575e82a1e285))

- Describe scale_mode in public terms; 'fixed' has no effect
  ([#131](https://github.com/BenHuddart/gleplot/pull/131),
  [`625aa95`](https://github.com/BenHuddart/gleplot/commit/625aa9535ab65786af8778e10c3104e25a898774))

- Mention the Windows GLE leg in the testing guide
  ([#102](https://github.com/BenHuddart/gleplot/pull/102),
  [`c38f936`](https://github.com/BenHuddart/gleplot/commit/c38f936930f04062be90ecf71e74ef734872a441))

- Prefer Cairo-safe TeX fonts in the font examples
  ([#128](https://github.com/BenHuddart/gleplot/pull/128),
  [`6610b31`](https://github.com/BenHuddart/gleplot/commit/6610b31eaf1c3b2a9ec28a68aff86bdcebfcb18d))

- Use GLE font names in the configuration docs
  ([#128](https://github.com/BenHuddart/gleplot/pull/128),
  [`3805ca3`](https://github.com/BenHuddart/gleplot/commit/3805ca3ee4e3e51c41fa61f41ce69e5a9275aff6))


## v5.6.1 (2026-11-19)

### Bug Fixes

- Accept matplotlib grey-level strings as colours
  ([#193](https://github.com/BenHuddart/gleplot/pull/193),
  [`81ec0a7`](https://github.com/BenHuddart/gleplot/commit/81ec0a7163b61b5bb2f82f9d0cbe6c62edb56714))

- Keep a raw constant-error dataset defined when its file is re-saved
  ([`d76f89e`](https://github.com/BenHuddart/gleplot/commit/d76f89eeff635d26386655c6d418dc3859b72d14))

- List grey-level strings in the colour fidelity contract
  ([#193](https://github.com/BenHuddart/gleplot/pull/193),
  [`ff3ce5e`](https://github.com/BenHuddart/gleplot/commit/ff3ce5e6ff248cfa11e2a427cd0557b50434a23d))

- Plot() honours lw/ls/c/ms and warns on keywords it ignores
  ([#166](https://github.com/BenHuddart/gleplot/pull/166),
  [`025697b`](https://github.com/BenHuddart/gleplot/commit/025697bd026c59117a883446b24f4e79013cb9fd))

- Read a numpy RGB(A) array as a colour ([#244](https://github.com/BenHuddart/gleplot/pull/244),
  [`1127994`](https://github.com/BenHuddart/gleplot/commit/1127994d0a9b4a1476551036012b93b84a9c89cf))

- Read a numpy RGB(A) array as one hist colour
  ([#244](https://github.com/BenHuddart/gleplot/pull/244),
  [`b4dc551`](https://github.com/BenHuddart/gleplot/commit/b4dc551e04b68acddd3e0124f2371cc2ce1b2dda))

- Review fixes for plot keyword handling ([#166](https://github.com/BenHuddart/gleplot/pull/166),
  [`24499cc`](https://github.com/BenHuddart/gleplot/commit/24499ccdf6e920c0e9ddb83bf70f3ce29f63b181))

### Documentation

- Address review of the README rewrite ([#103](https://github.com/BenHuddart/gleplot/pull/103),
  [`4a48619`](https://github.com/BenHuddart/gleplot/commit/4a48619be5f88a7453d918b4952c5495e6acd2f8))

- Record release policy in AGENTS.md ([#263](https://github.com/BenHuddart/gleplot/pull/263),
  [`0945f13`](https://github.com/BenHuddart/gleplot/commit/0945f134a6a10b53e736a1b158b0f05352d22164))

- Rewrite the README to show what gleplot is for
  ([#103](https://github.com/BenHuddart/gleplot/pull/103),
  [`6526832`](https://github.com/BenHuddart/gleplot/commit/652683241bfea1e4c13449344d410b4f1ed015d6))

- Separate unknown keyword names from junk values in release policy
  ([#263](https://github.com/BenHuddart/gleplot/pull/263),
  [`bd75a92`](https://github.com/BenHuddart/gleplot/commit/bd75a9279bba7cfe703d26dc75796cfe335aa141))


## v5.6.0 (2026-11-19)


## v5.5.0 (2026-11-19)

### Features

- Colorbar for a colour-mapped scatter ([#89](https://github.com/BenHuddart/gleplot/pull/89),
  [`fc22c9f`](https://github.com/BenHuddart/gleplot/commit/fc22c9f5b177e822530b26ed607cc6871a4f9335))

- Review fixes for the scatter colorbar ([#89](https://github.com/BenHuddart/gleplot/pull/89),
  [`802f869`](https://github.com/BenHuddart/gleplot/commit/802f86905cf66be313cb647fffa95337495b11d7))


## v5.4.0 (2026-11-19)

### Features

- Pcolormesh draws each cell of a uniform grid (#90, stage 1 of 2)
  ([`9d50b5a`](https://github.com/BenHuddart/gleplot/commit/9d50b5ae1cc00aa35da1d22e67a2d0fcdff034e8))

- Review fixes for pcolormesh ([#90](https://github.com/BenHuddart/gleplot/pull/90),
  [`99087e6`](https://github.com/BenHuddart/gleplot/commit/99087e61d2942e9fbe5f3b45efe46f5978cc5b6e))


## v5.3.0 (2026-11-19)


## v5.2.0 (2026-11-19)

### Features

- Per-point scatter colours with c=, cmap=, vmin= and vmax=
  ([#89](https://github.com/BenHuddart/gleplot/pull/89),
  [`675dbdf`](https://github.com/BenHuddart/gleplot/commit/675dbdfc43109b5b149610598dd43683da3956a0))

- Review fixes for per-point scatter colours ([#89](https://github.com/BenHuddart/gleplot/pull/89),
  [`fe42ab0`](https://github.com/BenHuddart/gleplot/commit/fe42ab09a9904f9f26ecafe28ec504db3aa69a8b))


## v5.1.0 (2026-11-19)

### Features

- Place an inset with Figure.add_axes(rect)
  ([`bb6a364`](https://github.com/BenHuddart/gleplot/commit/bb6a364d3d5236777481ea3941c9fae29770ded0))

- Record add_axes insets in the metadata header
  ([#85](https://github.com/BenHuddart/gleplot/pull/85),
  [`fa6b809`](https://github.com/BenHuddart/gleplot/commit/fa6b809c0dbdea83df6cc334904462d2f8f3f9b5))

- Review fixes for add_axes insets ([#85](https://github.com/BenHuddart/gleplot/pull/85),
  [`84d5419`](https://github.com/BenHuddart/gleplot/commit/84d5419d796daa5598c47a6f9c5f7f8058343353))

- Review fixes for spanning add_subplot ([#85](https://github.com/BenHuddart/gleplot/pull/85),
  [`16eff6c`](https://github.com/BenHuddart/gleplot/commit/16eff6c382196b02ba14fc26192cda8afa2ca509))

- Span several grid cells with add_subplot(rows, cols, (first, last))
  ([`e3b48a0`](https://github.com/BenHuddart/gleplot/commit/e3b48a03c30e7549e57457892fa4c98b06d2f55a))


## v5.0.0 (2026-11-19)

### Features

- Figure-level suptitle, text and legend ([#84](https://github.com/BenHuddart/gleplot/pull/84),
  [`9fba7cd`](https://github.com/BenHuddart/gleplot/commit/9fba7cd1c0c4779130ed93933ca0158bbc3b7b6c))

- Review fixes for figure-level text and legend
  ([#84](https://github.com/BenHuddart/gleplot/pull/84),
  [`8263642`](https://github.com/BenHuddart/gleplot/commit/826364270fd519fc8839e739304c60b828f4f1ea))


## v4.10.0 (2026-11-18)

### Features

- Place ax.text in axes fractions with transform=ax.transAxes
  ([#84](https://github.com/BenHuddart/gleplot/pull/84),
  [`d5ee6cb`](https://github.com/BenHuddart/gleplot/commit/d5ee6cbf18483b577f1a96cfd5c68aac2d3e5e19))

- Review fixes for axes-fraction text ([#84](https://github.com/BenHuddart/gleplot/pull/84),
  [`8ae8e11`](https://github.com/BenHuddart/gleplot/commit/8ae8e1130e82baf04f7cb068994992088ae7fff7))


## v4.9.0 (2026-11-18)

### Features

- Reversed colormap names (cmap="RdBu_r") ([#179](https://github.com/BenHuddart/gleplot/pull/179),
  [`c6cbd23`](https://github.com/BenHuddart/gleplot/commit/c6cbd23548ec92f7264b96b9a2d65d080ae63f52))

- Review fixes for reversed colormap names ([#179](https://github.com/BenHuddart/gleplot/pull/179),
  [`4044569`](https://github.com/BenHuddart/gleplot/commit/404456956002372351bb64d654172c870f842d69))


## v4.8.0 (2026-11-18)

### Features

- Hide an axis line with set_axis_line(visible=False)
  ([#83](https://github.com/BenHuddart/gleplot/pull/83),
  [`7bc457b`](https://github.com/BenHuddart/gleplot/commit/7bc457b77a71c384578fd9b758907a2e8edcadad))

- Review fixes for hidden axis lines ([#83](https://github.com/BenHuddart/gleplot/pull/83),
  [`4a44fc7`](https://github.com/BenHuddart/gleplot/commit/4a44fc717768dc2ef5bebb1651800684a57c5adc))


## v4.7.0 (2026-11-18)

### Features

- Matplotlib axis helpers twinx, invert_*axis, semilog*, set_*ticklabels, axis
  ([#81](https://github.com/BenHuddart/gleplot/pull/81),
  [`97a75a9`](https://github.com/BenHuddart/gleplot/commit/97a75a98aa7c1bc29e8d146a14e9ac0dcd666f3f))

- Review fixes for the axis helpers ([#81](https://github.com/BenHuddart/gleplot/pull/81),
  [`2668576`](https://github.com/BenHuddart/gleplot/commit/266857621d391adf28a3a4db816b113da2385224))


## v4.6.0 (2026-11-18)

### Features

- Fit results in the legend with Axes.fit label placeholders
  ([#75](https://github.com/BenHuddart/gleplot/pull/75),
  [`6546a26`](https://github.com/BenHuddart/gleplot/commit/6546a2664dc8879805c6603b6b6195b741e776b4))

- Review fixes for fit result legends ([#75](https://github.com/BenHuddart/gleplot/pull/75),
  [`1c4a429`](https://github.com/BenHuddart/gleplot/commit/1c4a4294ab2ed718df52db56ebe59d09f618fbdc))


## v4.5.0 (2026-11-18)

### Features

- Review fixes for Axes.rug ([#57](https://github.com/BenHuddart/gleplot/pull/57),
  [`b1a41b0`](https://github.com/BenHuddart/gleplot/commit/b1a41b07b02db3288012c0f52d6d4699154414ca))

- Rugs with Axes.rug ([#57](https://github.com/BenHuddart/gleplot/pull/57),
  [`146cbd1`](https://github.com/BenHuddart/gleplot/commit/146cbd17d8426a45436c6ae9618164fcc6d9f14c))


## v4.4.0 (2026-11-18)

### Features

- Axes.image raises NotImplementedError on a polar axes
  ([#59](https://github.com/BenHuddart/gleplot/pull/59),
  [`895f3c7`](https://github.com/BenHuddart/gleplot/commit/895f3c7895d08187a93a8b7b04314621f091ace9))

- Place image files in data coordinates with Axes.image
  ([#59](https://github.com/BenHuddart/gleplot/pull/59),
  [`ec71e09`](https://github.com/BenHuddart/gleplot/commit/ec71e09b4a72547a93716ff637b8f8881a6d6f04))

- Review fixes for Axes.image ([#59](https://github.com/BenHuddart/gleplot/pull/59),
  [`b57b781`](https://github.com/BenHuddart/gleplot/commit/b57b7810bf6745deae2d38901b636971c2857dee))


## v4.3.0 (2026-11-18)

### Features

- Heatmap from an expression with Axes.function2d
  ([#77](https://github.com/BenHuddart/gleplot/pull/77),
  [`04e3104`](https://github.com/BenHuddart/gleplot/commit/04e31040b0be299548789a68a1c2d526698bb62e))

- Review fixes for function2d ([#77](https://github.com/BenHuddart/gleplot/pull/77),
  [`83b6542`](https://github.com/BenHuddart/gleplot/commit/83b6542e453b3cc9ea0e9dc13b62e2e55979c50e))


## v4.2.0 (2026-11-18)

### Features

- Guard Axes.derived on a polar axes ([#58](https://github.com/BenHuddart/gleplot/pull/58),
  [`32d0ec3`](https://github.com/BenHuddart/gleplot/commit/32d0ec3b9b6b80f5fd66cf429f07091c25e8d7db))

- Polar angle labels under usetex ([#58](https://github.com/BenHuddart/gleplot/pull/58),
  [`d25333a`](https://github.com/BenHuddart/gleplot/commit/d25333a2ad9cf24a509d5fc4dcb62c3b09c57a53))

- Polar axes with add_subplot(projection='polar')
  ([#58](https://github.com/BenHuddart/gleplot/pull/58),
  [`0aafacd`](https://github.com/BenHuddart/gleplot/commit/0aafacde45f4cd24f00b1ecd37038b4aa4ff7b54))

- Polar scatters with per-point sizes, tick methods guarded
  ([#58](https://github.com/BenHuddart/gleplot/pull/58),
  [`b7df619`](https://github.com/BenHuddart/gleplot/commit/b7df619a0cc7de7c5d72dbd3cc52725e005f8384))

- Review fixes for polar axes ([#58](https://github.com/BenHuddart/gleplot/pull/58),
  [`09acc50`](https://github.com/BenHuddart/gleplot/commit/09acc50d714a3c9446e32bea1b1af6d56d8d6711))


## v4.1.0 (2026-11-18)

### Features

- Curves computed from other series with Axes.derived
  ([#76](https://github.com/BenHuddart/gleplot/pull/76),
  [`4c87fe0`](https://github.com/BenHuddart/gleplot/commit/4c87fe0d5f909ee965ca30576221c794c005bfb4))

- Free page drawing with Figure.circle, ellipse, arc, bezier, curve, polygon, table and tex
  ([#60](https://github.com/BenHuddart/gleplot/pull/60),
  [`9402ff9`](https://github.com/BenHuddart/gleplot/commit/9402ff9ba5c882dccb4b7f82a738b088ae649308))

- Per-point marker sizes for scatter ([#70](https://github.com/BenHuddart/gleplot/pull/70),
  [`d2394af`](https://github.com/BenHuddart/gleplot/commit/d2394af296e99192102428254bd57dc5ede99a40))


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
