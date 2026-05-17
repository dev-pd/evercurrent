import next from "eslint-config-next";
import prettier from "eslint-config-prettier";

const config = [
  ...next,
  prettier,
  {
    rules: {
      "react/jsx-curly-brace-presence": ["error", "never"],
      "no-console": ["warn", { allow: ["warn", "error"] }],
      eqeqeq: ["error", "always", { null: "ignore" }],
    },
  },
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts", "public/**"],
  },
];

export default config;
