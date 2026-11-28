// 字体: 日本語は Noto Sans JP、コード・URL・16 進数は Noto Sans Mono（どちらも Google Fonts、SIL Open Font License）。
// @remotion/google-fonts は読み込みが終わるまで書き出しを待つ。太さは DESIGN.md の 400 と 700 だけを読む。
// 字体の指定は Tailwind の font-sans・font-mono（src/styles/globals.css の --font-sans・--font-mono）で行う。
// 書き出しのときに Google Fonts から読むので、ネットワークにつながっている必要がある。
import { loadFont as loadNotoSansJP } from "@remotion/google-fonts/NotoSansJP";
import { loadFont as loadNotoSansMono } from "@remotion/google-fonts/NotoSansMono";

loadNotoSansJP("normal", { weights: ["400", "700"] });
loadNotoSansMono("normal", { weights: ["400", "700"], subsets: ["latin"] });
