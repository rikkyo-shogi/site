// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// GitHub Pages では base を /<repo-name>/ に設定する
// 独自ドメイン(rikkyo-shogi.github.io)の場合は base: '/' のまま
export default defineConfig({
  site: 'https://rikkyo-shogi.github.io/site',
  base: '/site',
  output: 'static',
  integrations: [
    sitemap({
      // 検証中で検索エンジンにインデックスさせたくないページを除外(推測しづらいランダムなURL)
      filter: (page) => !page.includes('/shadan/7e17dd82aaf680d86043caf3'),
    }),
  ],
});
