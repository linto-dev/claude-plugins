/**
 * Remotion Studio と CLI（npx remotion render）の設定。
 * Node の API（scripts/review.ts の bundle()）はこのファイルを読まないので、同じ別名と Tailwind の設定を scripts/bundle.ts で渡している。
 *
 * All configuration options: https://remotion.dev/docs/config
 */
import { Config } from "@remotion/cli/config";
import { withProjectBundler } from "./scripts/bundle.ts";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);
Config.overrideBundlerConfig(withProjectBundler);
