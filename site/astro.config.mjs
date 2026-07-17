// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// GitHub Pages では base を /<repo-name>/ に設定する
// 独自ドメイン(rikkyo-shogi.github.io)の場合は base: '/' のまま
export default defineConfig({
  site: 'https://rikkyo-shogi.github.io/site',
  base: '/site',
  output: 'static',
  integrations: [sitemap()],
});
