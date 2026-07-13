type GoogleCredentialResponse = { credential: string };

type GoogleIdApi = {
  initialize(config: {
    client_id: string;
    callback(response: GoogleCredentialResponse): void;
  }): void;
  renderButton(
    parent: HTMLElement,
    options: {
      locale: string;
      shape: "rectangular";
      size: "large";
      text: "continue_with";
      theme: "outline";
      width: number;
    },
  ): void;
};

interface Window {
  google: { accounts: { id: GoogleIdApi } };
}
