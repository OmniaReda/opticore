import { Component } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink],
  template: `
    <nav class="navbar navbar-dark bg-dark mb-4">
      <div class="container">
        <a class="navbar-brand fw-semibold" routerLink="/projects">OPTICORE</a>
        <span class="navbar-text small">FTTH/ODN design · prototype</span>
      </div>
    </nav>
    <main class="container pb-5">
      <router-outlet />
    </main>
  `,
})
export class App {}
