import type { Config } from 'tailwindcss';

/**
 * 设计基调（与产品方向一致）：干净书页风
 *  - 暖白底（#fdfaf5）+ 深灰文字（#1f1d1a）
 *  - 暖橘强调色（#c2410c）呼应"故事 / 剧情"产品气质
 *  - 移动端优先（与 02-前端需求文档.md G12 对齐）
 */
const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // 品牌色板
        paper: '#fdfaf5',
        ink: {
          DEFAULT: '#1f1d1a',
          soft: '#6b6457',
        },
        accent: {
          DEFAULT: '#c2410c',
          hover: '#a13609',
        },
        border: {
          subtle: '#e7e1d4',
        },
        ok: '#2e7d32',
        danger: '#b91c1c',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'sans-serif',
        ],
        serif: [
          'Source Han Serif SC',
          'Noto Serif CJK SC',
          'Songti SC',
          'serif',
        ],
        mono: [
          'ui-monospace',
          'SF Mono',
          'Cascadia Mono',
          'Menlo',
          'Consolas',
          'monospace',
        ],
      },
    },
  },
  plugins: [],
};

export default config;
